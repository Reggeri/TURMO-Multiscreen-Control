# v0.28.34 – Frissítő javítása

- A program címsorában és verzióellenőrzésében 0.28.34 szerepel.
- A frissítő külön PowerShell-folyamatban várja a régi EXE folyamatának teljes leállását (legfeljebb 90 másodperc). Ha nem áll le, a frissítés nem írja felül és nem indítja el a régi EXE-t.
- Sikeres EXE-csere után a Windows Asztal ismert mappájában TURMO Control.lnk parancsikont hoz létre vagy frissít.
- Csak sikeres csere után indítja az új EXE-t. Az esetleges hibák a letöltés ideiglenes mappájának install-result.log fájljába kerülnek.
- Az EXE felülírásához megfelelő Windows jogosultság szükséges.
- Az új frissítőlogika a v0.28.34-ben lép életbe; a régebbi verzió frissítője végzi a v0.28.34 első telepítését.
