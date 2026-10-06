"""Rebuild ``src/data/cities.tsv.gz`` from GeoNames (https://www.geonames.org, CC BY 4.0).

    python scripts/build_cities.py

Keeps every populated place of at least 1,000 people, with its country code, first-level
division name (state or province), name, coordinates (3 decimals, about 100 m) and population.
"""

import csv
import gzip
import io
import urllib.request
import zipfile
from pathlib import Path

GEONAMES = "https://download.geonames.org/export/dump/"
OUTPUT = Path(__file__).resolve().parent.parent / "src" / "data" / "cities.tsv.gz"


def _download(name: str) -> bytes:
    with urllib.request.urlopen(GEONAMES + name, timeout=120) as response:
        return response.read()


def main() -> None:
    admin1: dict[str, str] = {}
    for line in _download("admin1CodesASCII.txt").decode("utf-8").splitlines():
        key, _name, ascii_name, _id = line.split("\t")
        admin1[key] = ascii_name
    archive = zipfile.ZipFile(io.BytesIO(_download("cities1000.zip")))
    rows = []
    with archive.open("cities1000.txt") as raw:
        for fields in csv.reader(
            io.TextIOWrapper(raw, "utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE
        ):
            country, admin1_code = fields[8], fields[10]
            rows.append(
                (
                    country,
                    admin1.get(f"{country}.{admin1_code}", ""),
                    fields[2],  # ASCII name
                    f"{float(fields[4]):.3f}",
                    f"{float(fields[5]):.3f}",
                    fields[14] or "0",
                )
            )
    rows.sort()
    with gzip.open(OUTPUT, "wt", encoding="utf-8", compresslevel=9) as out:
        out.write("country\tdivision\tname\tlatitude\tlongitude\tpopulation\n")
        out.writelines("\t".join(row) + "\n" for row in rows)
    print(f"Wrote {len(rows)} places to {OUTPUT}")


if __name__ == "__main__":
    main()
