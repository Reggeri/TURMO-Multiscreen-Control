# v0.28.25 – Compact Video Mode

A videó 96×72 képpontos, középre helyezett ablakban jelenik meg. A képkocka teljes egészében kerül átküldésre egyetlen RGB565 téglalapként, ezért nincsenek külön kirajzolódó blokkok vagy képsávok.

Képkockánként 13,5 KiB képadat, szemben a korábbi 320×240-as ablak 150 KiB-jával. Ez jelentősen csökkenti a szükséges USB-adatátvitelt, de a kép kisebb lesz. A 25 FPS nem garantált: a korábban mért 125–220 KiB/s mellett az elméleti felső korlát kb. 9–16 FPS (protokoll overhead nélkül).

A normál témák és a Full Screen EQ kódja nem változott.
