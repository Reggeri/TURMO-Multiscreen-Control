# Video Scanline Mode – v0.28.22

A Video Player most teljes szélességű vízszintes sávokat frissít, sorrendben, a korábbi 32×16-os mozaikok helyett. A sávok száma a TURMO_VIDEO_BUDGET_KIB környezeti változóval állítható (alapérték 12 KiB). A többi téma és az EQ send() útvonala változatlan.

Ez a frissítés a blokkok látványát célozza, nem növeli a soros kapcsolat sávszélességét. Gyors mozgásnál vízszintes képtörés látszódhat.
