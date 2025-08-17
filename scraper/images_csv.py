# -*- coding: utf-8 -*-
"""
Scraper d'images + export CSV WooCommerce (parent + variations/couleurs)
-> Convertit toutes les images en .JPG (qualité configurable)
-> (Mode 'wp-upload') Uploade automatiquement les .JPG dans WordPress (REST API + Application Password)
-> (Mode 'wp-prefix') Construit des URLs propres au site sans upload
-> Écrit/alimente UN SEUL CSV maître: exports/FICHE PRODUIT PLANETE BOB.csv
   (UPSERT par SKU, entête unique, UTF-8 avec BOM)

Modes d'images disponibles pour la colonne CSV "Images":
- source       : garde les URLs d'origine (attention : peuvent être .webp/.png)
- wp-upload    : upload auto vers WP, écrit les URLs "source_url" retournées
- wp-prefix    : N'upload pas ; construit des URLs propres au site à partir des JPG générés
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import re
import sys
import time
import traceback
import unicodedata
from io import BytesIO
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple, Callable
from urllib.parse import urljoin, urlparse

import requests
from PIL import Image, UnidentifiedImageError
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager  # type: ignore

# ----- Config -----
LAZY_ATTRS = ["src", "data-src", "data-lazy", "data-original", "data-srcset", "srcset"]
CSV_EXPORT_DIR = Path("exports")
CSV_MASTER_NAME = "FICHE PRODUIT PLANETE BOB.csv"
DEFAULT_OUT_DIR = Path("images")
WP_UPLOAD_CACHE = CSV_EXPORT_DIR / "wp_upload_cache.json"   # cache SHA1 -> {url,id,filename}

# Couleurs FR (slugifiées)
KNOWN_COLOR_SLUGS: Set[str] = {
    "noir","blanc","beige","gris","jaune","rouge","rose",
    "bleu","bleu-fonce","bleu-clair","bleu-marine","marine",
    "vert","kaki","camel","marron","violet","orange",
    "bordeaux","ecru","taupe","dore","argent","imprime","multicolore",
}
COLOR_STOPWORDS: Set[str] = {"bob","chapeau","casquette","bonnet","taille","unique","standard"}

# ---------- utilitaires ----------
def slugify(s: str) -> str:
    s = s.strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "produit"

def safe_dirname(name: str) -> str:
    name = name.strip()
    if not name:
        return "produit"
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name).strip(" .")
    return name or "produit"

def title_from_url(url: str) -> str:
    slug = os.path.basename(urlparse(url).path.rstrip("/")) or "produit"
    slug = slug.replace("-", " ").replace("_", " ")
    return slug.title()

def strip_trailing_number(base: str) -> str:
    return re.sub(r"-\d+$", "", base)

def best_from_srcset(srcset_value: str) -> str | None:
    try:
        parts = [p.strip() for p in srcset_value.split(",")]
        pairs: List[Tuple[str, int]] = []
        for p in parts:
            tokens = p.split()
            if not tokens: continue
            url = tokens[0]; size = 0
            if len(tokens) >= 2 and tokens[1].endswith("w"):
                try: size = int(tokens[1][:-1])
                except Exception: size = 0
            pairs.append((url, size))
        if not pairs: return None
        pairs.sort(key=lambda x: x[1])
        return pairs[-1][0]
    except Exception:
        return None

# ---------- Chrome/Selenium ----------
def auto_chrome(headless: bool = True, timeout: int = 30) -> webdriver.Chrome:
    chrome_opts = ChromeOptions()
    if headless: chrome_opts.add_argument("--headless=new")
    chrome_opts.add_argument("--disable-gpu")
    chrome_opts.add_argument("--no-sandbox")
    chrome_opts.add_argument("--disable-dev-shm-usage")
    chrome_opts.add_argument("--window-size=1920,1080")
    chrome_opts.add_argument("--disable-blink-features=AutomationControlled")
    chrome_opts.add_argument("--disable-extensions")
    chrome_opts.add_argument("--disable-notifications")
    chrome_opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_opts.add_experimental_option("useAutomationExtension", False)
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_opts)
    driver.set_page_load_timeout(timeout)
    return driver

def smart_scroll(driver, max_passes: int = 12, pause: float = 0.75) -> None:
    last_height = 0
    for _ in range(max_passes):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause)
        new_height = driver.execute_script("return document.body.scrollHeight") or 0
        try: new_height = int(float(new_height))
        except Exception: new_height = 0
        if new_height <= last_height: break
        last_height = new_height

# ---------- extraction images + infos ----------
def extract_image_url_from_element(el, base_url: str) -> str | None:
    tag = (el.tag_name or "").lower()
    try:
        for attr in ("srcset", "data-srcset"):
            val = (el.get_attribute(attr) or "").strip()
            if val:
                best = best_from_srcset(val)
                if best:
                    return urljoin(base_url, best)
    except Exception:
        pass
    if tag == "img":
        for attr in ("data-src", "data-lazy", "data-original", "src"):
            val = (el.get_attribute(attr) or "").strip()
            if val:
                return urljoin(base_url, val)
    try:
        style = (el.get_attribute("style") or "").strip()
        if "background-image" in style:
            m = re.search(r'background-image\s*:\s*url\((["\']?)(.+?)\1\)', style, re.I)
            if m:
                return urljoin(base_url, m.group(2))
    except Exception:
        pass
    if tag == "source":
        srcset = (el.get_attribute("srcset") or "").strip()
        if srcset:
            best = best_from_srcset(srcset)
            if best:
                return urljoin(base_url, best)
    return None

def detect_product_title(driver, url: str) -> str:
    for sel in ["meta[property='og:title']","meta[name='og:title']","meta[name='twitter:title']"]:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            val = (el.get_attribute("content") or "").strip()
            if val: return val
        except Exception:
            pass
    for sel in ["h1",".product-title",".product__title","[data-product-title]",
                ".product-name",".ProductMeta__Title",".product-single__title"]:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            txt = (el.text or "").strip()
            if txt: return txt
        except Exception:
            pass
    return title_from_url(url)

def fetch_images_with_meta(url: str, css_selector: str, headless: bool=True,
                           scroll_passes: int=10, wait_css: str|None=None,
                           page_timeout: int=30) -> Tuple[List[Dict[str,str]], str, str]:
    driver = auto_chrome(headless=headless, timeout=page_timeout)
    try:
        driver.get(url)
        title = detect_product_title(driver, url)
        slug  = slugify(title)
        if wait_css:
            try:
                WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, wait_css)))
            except Exception:
                pass
        smart_scroll(driver, max_passes=scroll_passes)
        base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        elements = driver.find_elements(By.CSS_SELECTOR, css_selector)

        seen: Set[str] = set()
        items: List[Dict[str,str]] = []
        for el in elements:
            img_el = el
            if el.tag_name.lower() != "img":
                try:
                    img_el = el.find_element(By.CSS_SELECTOR, "img")
                except Exception:
                    img_el = el
            img_url = extract_image_url_from_element(img_el, base_url)
            if not img_url or img_url in seen:
                continue
            seen.add(img_url)
            alt = (img_el.get_attribute("alt") or "").strip()
            base = os.path.basename(urlparse(img_url).path)
            items.append({"url": img_url, "alt": alt, "basename": base})
        return items, title, slug
    finally:
        driver.quit()

# ---------- téléchargement + conversion JPG ----------
def unique_name_no_digits(base: str, ext: str, used: Set[str]) -> str:
    cand = f"{base}{ext}"
    if cand.lower() not in used:
        used.add(cand.lower()); return cand
    alphabet = [chr(c) for c in range(ord("a"), ord("z")+1)]
    for a in alphabet:
        cand = f"{base}-{a}{ext}"
        if cand.lower() not in used:
            used.add(cand.lower()); return cand
    for a in alphabet:
        for b in alphabet:
            cand = f"{base}-{a}{b}{ext}"
            if cand.lower() not in used:
                used.add(cand.lower()); return cand
    i = 1
    while True:
        cand = f"{base}-x{i}{ext}"
        if cand.lower() not in used:
            used.add(cand.lower()); return cand
        i += 1

def _to_jpeg(img: Image.Image, quality: int) -> bytes:
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
        out_img = bg
    else:
        out_img = img.convert("RGB")
    buf = BytesIO()
    out_img.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    return buf.getvalue()

def download_and_convert_to_jpg(urls: Iterable[str], out_dir: Path, quality: int=90, timeout: int=20) -> List[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    used: Set[str] = set()
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    saved_names: List[str] = []
    for u in urls:
        filename = ""
        try:
            resp = s.get(u, timeout=timeout)
            resp.raise_for_status()
            path = urlparse(u).path
            base_with_ext = os.path.basename(path) or "image"
            base, _ = os.path.splitext(base_with_ext)
            base_no_num = strip_trailing_number(base) or "image"
            final_name = unique_name_no_digits(base_no_num, ".jpg", used)
            final_path = out_dir / final_name
            img = Image.open(BytesIO(resp.content))
            jpg_bytes = _to_jpeg(img, quality=quality)
            with open(final_path, "wb") as f:
                f.write(jpg_bytes)
            print(f"[OK] {u}  ->  {final_path}")
            filename = final_name
        except UnidentifiedImageError as e:
            print(f"[ERR] {u} : Image illisible ({e})")
        except Exception as e:
            print(f"[ERR] {u} : {e}")
        saved_names.append(filename)
    return saved_names

# ---------- Upload WordPress (REST /wp-json/wp/v2/media) ----------
def _wp_auth_header(user: str, app_pass: str) -> str:
    token = f"{user}:{app_pass}".encode("utf-8")
    return "Basic " + base64.b64encode(token).decode("ascii")

def _sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def _load_cache(path: Path) -> Dict[str, Dict[str, str]]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def _save_cache(path: Path, data: Dict[str, Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def upload_jpgs_to_wp(site: str, user: str, app_pass: str, local_dir: Path, filenames: List[str],
                      product_title: str="", timeout: int=30) -> Dict[str, str]:
    if not site.endswith("/"):
        site += "/"
    endpoint = site + "wp-json/wp/v2/media"
    headers_auth = {"Authorization": _wp_auth_header(user, app_pass)}
    cache = _load_cache(WP_UPLOAD_CACHE)
    out: Dict[str, str] = {}
    for fname in filenames:
        if not fname:
            out[fname] = ""
            continue
        fpath = local_dir / fname
        if not fpath.exists():
            out[fname] = ""
            continue
        sha1 = _sha1_file(fpath)
        if sha1 in cache:
            out[fname] = cache[sha1].get("url", "")
            print(f"[SKIP] déjà uploadé (cache) : {fname} -> {out[fname]}")
            continue
        try:
            data = fpath.read_bytes()
            headers = {**headers_auth,
                       "Content-Disposition": f'attachment; filename="{fname}"',
                       "Content-Type": "image/jpeg"}
            r = requests.post(endpoint, headers=headers, data=data, timeout=timeout)
            if r.status_code not in (200, 201):
                print(f"[ERR] upload {fname}: {r.status_code} {r.text[:200]}")
                out[fname] = ""
                continue
            j = r.json()
            media_id = j.get("id")
            src_url = j.get("source_url", "")
            if media_id and product_title:
                meta = {"title": product_title, "alt_text": product_title}
                try:
                    requests.post(f"{endpoint}/{media_id}",
                                  headers={**headers_auth, "Content-Type": "application/json"},
                                  data=json.dumps(meta), timeout=timeout)
                except Exception:
                    pass
            out[fname] = src_url
            cache[sha1] = {"url": src_url, "id": str(media_id or ""), "filename": fname}
            _save_cache(WP_UPLOAD_CACHE, cache)
            print(f"[UP] {fname} -> {src_url}")
        except Exception as e:
            print(f"[ERR] upload {fname}: {e}")
            out[fname] = ""
    return out

# ---------- variantes/couleurs ----------
SIZE_TOKENS = {"m","l","xl","s","xs","xxl"}

def prettify_color_label(color_slug: str) -> str:
    txt = color_slug.replace("-", " ").strip().lower()
    txt = re.sub(r"\bfonce\b", "foncé", txt)
    return " ".join(w.capitalize() for w in txt.split())

def extract_color_from_filename(filename_no_ext: str, product_slug: str) -> str | None:
    base = strip_trailing_number(filename_no_ext)
    if not base.startswith(product_slug + "-"):
        return None
    rest = base[len(product_slug)+1:]
    tokens = rest.split("-")
    color_tokens: List[str] = []
    for t in tokens:
        if t in SIZE_TOKENS or re.fullmatch(r"\d+cm", t): break
        if re.fullmatch(r"\d+(cm)?", t): break
        color_tokens.append(t)
    if not color_tokens: return None
    return "-".join(color_tokens)

def extract_color_for_image(img: Dict[str,str], product_slug: str) -> Tuple[str|None, str|None]:
    base, _ = os.path.splitext(img["basename"])
    color_slug = extract_color_from_filename(base, product_slug)
    if color_slug and color_slug in KNOWN_COLOR_SLUGS:
        return color_slug, prettify_color_label(color_slug)
    alt = img.get("alt") or ""
    if alt:
        alt_clean = alt.lower()
        prod_words = product_slug.replace("-", " ")
        alt_clean = alt_clean.replace(prod_words, "").strip(" -–—_:()[]")
        alt_clean = re.sub(r"\s+", " ", alt_clean)
        if not alt_clean:
            return None, None
        cand = slugify(alt_clean)
        parts = [p for p in cand.split("-") if p and p not in COLOR_STOPWORDS]
        if not parts:
            return None, None
        cand = "-".join(parts)
        if cand in KNOWN_COLOR_SLUGS:
            return cand, prettify_color_label(cand)
    return None, None

def build_rows_auto_type(product_title: str, product_slug: str,
                         all_images: List[str], image_meta: List[Dict[str,str]],
                         url_transform: Callable[[str], str]=lambda u: u) -> List[List[str]]:
    color_to_image: Dict[str,str] = {}
    color_to_label: Dict[str,str] = {}
    for it in image_meta:
        color_slug, color_label = extract_color_for_image(it, product_slug)
        if color_slug and color_slug not in color_to_image:
            color_to_image[color_slug] = it["url"]
            color_to_label[color_slug] = color_label or color_slug.replace("-", " ").title()

    parent_imgs_list = [t for t in (url_transform(u) for u in all_images) if t]
    parent_images = ", ".join(parent_imgs_list)

    if len(color_to_image) < 2:
        return [[
            "", "simple", product_slug, product_title, "1", "visible", "taxable", "1",
            parent_images, "", "", "", "", "", "", "",
        ]]

    color_labels_ordered = [color_to_label[c] for c in color_to_image.keys()]
    rows: List[List[str]] = [[
        "", "variable", product_slug, product_title, "1", "visible", "taxable", "1",
        parent_images, "", "", "", "couleur", ", ".join(color_labels_ordered), "1", "1",
    ]]
    for color_slug, orig_url in color_to_image.items():
        label = color_to_label.get(color_slug, prettify_color_label(color_slug))
        var_name = f"{product_title} - {label}"
        var_img = url_transform(orig_url)
        rows.append([
            "", "variation", f"{product_slug}-{color_slug}", var_name, "1", "visible", "taxable", "1",
            var_img, product_slug, "", "", "couleur", label, "1", "1",
        ])
    return rows

# ---------- CSV maître ----------
CSV_HEADERS = [
    "ID","Type","SKU","Name","Published","Visibility in catalog","Tax status",
    "In stock?","Images","Parent","Regular price","Sale price",
    "Attribute 1 name","Attribute 1 value(s)","Attribute 1 visible","Attribute 1 global",
]

def append_rows_to_master_csv(csv_path: Path, rows: List[List[str]]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    existing_rows: List[List[str]] = []
    header = CSV_HEADERS[:]
    if csv_path.exists():
        try:
            with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.reader(f)
                try:
                    file_header = next(reader)
                except StopIteration:
                    file_header = []
                if file_header and len(file_header) == len(header):
                    header = file_header
                for r in reader:
                    if len(r) < len(header): r = r + [""]*(len(header)-len(r))
                    elif len(r) > len(header): r = r[:len(header)]
                    existing_rows.append(r)
        except Exception:
            existing_rows = []
    try:
        sku_idx = header.index("SKU")
    except ValueError:
        sku_idx = 2
    index_by_sku: Dict[str,int] = {}
    for i,r in enumerate(existing_rows):
        if len(r) > sku_idx:
            sku = (r[sku_idx] or "").strip()
            if sku: index_by_sku[sku] = i
    upserted = 0; added = 0
    for row in rows:
        if len(row) < len(header): row = row + [""]*(len(header)-len(row))
        elif len(row) > len(header): row = row[:len(header)]
        sku = (row[sku_idx] or "").strip()
        if sku and sku in index_by_sku:
            existing_rows[index_by_sku[sku]] = row; upserted += 1
        else:
            existing_rows.append(row)
            if sku: index_by_sku[sku] = len(existing_rows)-1
            added += 1
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(existing_rows)
    print(f"CSV upsert: {upserted} mise(s) à jour, {added} ajoutée(s) → {csv_path.name}")

# ---------- helpers URLs propres (mode wp-prefix) ----------
def build_prefixed_urls(prefix: str, names: List[str], year: str|None=None, month: str|None=None) -> Dict[str, str]:
    """
    Retourne un dict {local_name -> full_url} en concaténant prefix + (/year/month)? + /name
    - prefix: ex "https://www.planetebob.fr/wp-content/uploads"
    - names: liste de noms de fichiers .jpg (peut contenir des "" pour échecs)
    """
    if prefix.endswith("/"):
        base = prefix[:-1]
    else:
        base = prefix
    suffix = ""
    if year and month:
        month = f"{int(month):02d}"
        suffix = f"/{year}/{month}"
    mapping: Dict[str, str] = {}
    for n in names:
        if not n:
            mapping[n] = ""
            continue
        mapping[n] = f"{base}{suffix}/{n}"
    return mapping

# ---------- main ----------
def main() -> None:
    ap = argparse.ArgumentParser(
        description="Scraper d'images + export CSV WooCommerce (simple/variable auto) + (wp-upload|wp-prefix)",
        add_help=True,
    )
    ap.add_argument("--url", default=None, help="URL à scraper")
    ap.add_argument("--css", default=None, help='Sélecteur CSS des images (ex: ".product-gallery__media-list img")')
    ap.add_argument("--wait-css", default=None, help="CSS à attendre avant collecte (optionnel)")
    ap.add_argument("--scroll", dest="scroll_passes", type=int, default=10, help="Nb de passes de scroll (def: 10)")
    ap.add_argument("--no-headless", action="store_true", help="Affiche le navigateur (désactive headless)")
    ap.add_argument("-o", "--out", default=str(DEFAULT_OUT_DIR), help='Dossier racine images (def: "images")')
    ap.add_argument("--csv", default=None, help="Chemin CSV maître (optionnel, sinon nom par défaut)")
    ap.add_argument("--images-mode", choices=["source", "wp-upload", "wp-prefix"], default="source",
                    help="'source' = URLs d'origine ; 'wp-upload' = upload auto WP ; 'wp-prefix' = URLs propres, sans upload")
    ap.add_argument("--wp-site", default="https://www.planetebob.fr", help="URL du site WP (https://...)")
    ap.add_argument("--wp-user", default="", help="Utilisateur WP (ayant un Application Password)")
    ap.add_argument("--wp-app-pass", default="", help="Application Password (coller tel quel, avec espaces)")
    ap.add_argument("--wp-prefix-url", default="https://www.planetebob.fr/wp-content/uploads",
                    help="Préfixe des URLs images pour 'wp-prefix' (défaut: /wp-content/uploads)")
    ap.add_argument("--wp-year", default=None, help="Année pour /year/month dans 'wp-prefix' (optionnel)")
    ap.add_argument("--wp-month", default=None, help="Mois (01..12) pour /year/month dans 'wp-prefix' (optionnel)")
    ap.add_argument("--jpg-quality", type=int, default=90, help="Qualité JPEG (def: 90)")

    args = ap.parse_args()
    print(f"[DEBUG] mode={args.images_mode} site={args.wp_site}")

    url = (args.url or "").strip()
    css = (args.css or "").strip()
    if not url: url = input("👉 Entre l'URL à scraper : ").strip()
    if not css: css = input("👉 Entre le sélecteur CSS (ex: .product-gallery__media-list img) : ").strip()
    if not url or not css:
        print("URL et sélecteur CSS sont obligatoires. Abandon."); sys.exit(2)
    if not urlparse(url).scheme:
        url = "https://" + url

    headless = not args.no_headless

    try:
        image_meta, product_title, product_slug = fetch_images_with_meta(
            url=url, css_selector=css, headless=headless,
            scroll_passes=args.scroll_passes, wait_css=args.wait_css,
        )
        if not image_meta:
            print("Aucune image trouvée."); return

        print(f"Titre produit : {product_title}")
        print(f"Slug produit  : {product_slug}")
        all_urls = [m["url"] for m in image_meta]
        print(f"{len(all_urls)} image(s) détectée(s).")

        # 1) Téléchargements + conversion JPG
        root_dir = Path(args.out)
        product_dir = root_dir / safe_dirname(product_title)
        print(f"Téléchargement vers : {product_dir.resolve()}")
        saved_names_jpg = download_and_convert_to_jpg(all_urls, product_dir, quality=args.jpg_quality)

        # 1bis) map URL d'origine -> valeur "Images" dans le CSV
        url_map: Dict[str, str] = {}

        if args.images_mode == "wp-upload":
            if args.wp_user and args.wp_app_pass:
                uploaded_map = upload_jpgs_to_wp(
                    site=args.wp_site,
                    user=args.wp_user,
                    app_pass=args.wp_app_pass,
                    local_dir=product_dir,
                    filenames=saved_names_jpg,
                    product_title=product_title,
                )
                for u, fname in zip(all_urls, saved_names_jpg):
                    url_map[u] = uploaded_map.get(fname, "")
            else:
                print("⚠️  Pas d'identifiants WP fournis → fallback en mode 'source' (URLs d'origine).")
                for u in all_urls:
                    url_map[u] = u

        elif args.images_mode == "wp-prefix":
            # construit des URLs propres au site sans upload
            prefixed = build_prefixed_urls(
                prefix=args.wp_prefix_url,
                names=saved_names_jpg,
                year=args.wp_year,
                month=args.wp_month,
            )
            for u, fname in zip(all_urls, saved_names_jpg):
                url_map[u] = prefixed.get(fname, "")

        else:
            # mode 'source'
            for u in all_urls:
                url_map[u] = u

        def url_transform(u: str) -> str:
            return url_map.get(u, u)

        # 2) Lignes CSV + UPSERT
        rows = build_rows_auto_type(product_title, product_slug, all_urls, image_meta, url_transform=url_transform)
        CSV_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        csv_path = Path(args.csv) if args.csv else (CSV_EXPORT_DIR / CSV_MASTER_NAME)
        append_rows_to_master_csv(csv_path, rows)

        print("✅ Terminé.")
    except Exception as e:
        print("Erreur:", e)
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
