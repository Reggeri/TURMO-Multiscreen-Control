# TURMO Control v0.28.18 – Videó

A Video fülön külön fájlt állíthatsz be mindkét kijelzőre. Támogatott formátumok: MP4, MKV, MOV, AVI és WEBM (az FFmpeg dekódolja).

1. Válaszd ki a fájlt a Browse video gombbal.
2. Válassz képillesztést: Cover (kitöltés/vágás), Contain (teljes kép/keret), Stretch (nyújtás).
3. Válassz dekódolási szélességet (160/240/320/480). A 240 jó kiindulás. A 160 pixeles kép láthatóan pixelesebb, de könnyebben dekódolható.
4. Válassz cél-FPS-t (15/20/25/30), majd Play on display.
5. A Diagnostics fülön nézd az „USB actual” FPS-t. Ez a valódi kijelzőnek elküldött képkockák száma másodpercenként.

A videó hang nélkül, végtelenítve megy. Az új videó kiválasztása újraindítja a kijelzők szálait, ezért a másik kijelző rövid időre megszakadhat.

FONTOS: 25 FPS teljes képernyőn 7,68 MB/s RGB565 adatot jelent. A dekódolási felbontás csökkentése NEM csökkenti ezt az USB-adatmennyiséget. Ha a kijelző vagy a soros-USB kapcsolat ennél lassabb, a 25 FPS fizikailag nem garantálható. A program a legfrissebb képkockát küldi, nem épít fel egyre hosszabb képkockasort. A meglévő Full Screen EQ adatküldéséhez nem nyúltunk.
