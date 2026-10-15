# v0.28.24 – Kísérleti videós változássor-küldés

A VIDEO PLAYER most csak a megváltozott képsorokat küldi át az ismert RGB565 / 197-es kijelzőparanccsal. Egymás melletti változott sorokat összevonja; teljesen változó jelenetnél ugyanakkora adatot kell küldeni, mint eddig. Ez **nem** hardveres JPEG/RLE tömörítés, mert ilyen parancs támogatása nincs igazolva.

A videó továbbra is középen, 320×240-as méretben jelenik meg. Az EQ és a normál témák változatlanok. Ha a videó szinte minden sora változik, érdemi FPS-növekedés nem várható. A képernyőn továbbra is lehet szakadás, mert nincs igazolt kettős puffer.
