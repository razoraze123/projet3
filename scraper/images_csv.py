import argparse

def main() -> None:
    ap = argparse.ArgumentParser(description="Stub images_csv")
    ap.add_argument("--url", default="", help="URL à scraper")
    ap.add_argument("--css", default="", help="Sélecteur CSS des images")
    ap.add_argument("--images-mode", default="wp-prefix")
    ap.add_argument("--wp-prefix-url", default="")
    args = ap.parse_args()

    print(f"Titre produit : {args.url}")
    print(f"Slug produit  : {args.url}")
    print("0 image(s) détectée(s).")
    print("CSV upsert: 0 mise(s) à jour, 0 ajoutée(s) → FICHE PRODUIT PLANETE BOB.csv")
    print("✅ Terminé.")


if __name__ == "__main__":
    main()
