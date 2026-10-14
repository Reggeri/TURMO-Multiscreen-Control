# TURMO Control feltöltése GitHubra

## 1. Nyilvános tároló létrehozása

1. Nyisd meg: https://github.com/new
2. **Repository name:** `TURMO-Control`
3. **Description:** `Open-source control software for 3.5-inch USB smart displays with hardware monitoring, music visualization and custom themes.`
4. **Visibility:** **Public**
5. Ne pipáld be a README, `.gitignore` és License automatikus létrehozását (a csomag tartalmazza őket).
6. Kattints a **Create repository** gombra.

## 2. Fájlok feltöltése (böngészőből)

1. Csomagold ki a `TURMO-Control-GitHub-v0.28.1.zip` fájlt.
2. A GitHub tárolóban kattints **uploading an existing file** vagy **Add file → Upload files**.
3. A **kicsomagolt mappa tartalmát** töltsd fel (ne a ZIP-et önmagában, és ne egy újabb almappába).
4. Ellenőrizd, hogy az `app.py`, `README.md`, `requirements.txt`, `build_windows.bat`, `sensor_bridge/` és `.github/workflows/windows-exe.yml` is felkerült.
5. Írd a commit üzenethez: `Initial public release v0.28.1` → **Commit changes**.

**Figyelem:** a GitHub webes feltöltése nem minden böngészőben kezeli jól a rejtett `.github` mappát. Ha a workflow nem került fel, a GitHubon hozz létre új fájlt pontosan ezen az útvonalon: `.github/workflows/windows-exe.yml`, majd másold be a csomagból a tartalmát.

## 3. Windows EXE elkészítése a GitHubon

1. A tárolóban nyisd meg az **Actions** fület.
2. Ha szükséges, engedélyezd a workflow-kat.
3. Válaszd ki a **Build TURMO Control Windows EXE** workflow-t.
4. Kattints **Run workflow** → **Run workflow**.
5. Sikeres futás után a futás oldalán az **Artifacts** részből töltsd le a `TURMO-Control-Windows-x64` csomagot.
6. A ZIP-ben ott lesz a `TURMO-Control.exe`.

## 4. Nyilvános kiadás (Release)

1. A tárolóban kattints a **Releases → Create a new release** lehetőségre.
2. **Tag:** `v0.28.1`
3. **Release title:** `TURMO Control v0.28.1`
4. Csatold az Actionsből letöltött `TURMO-Control.exe` fájlt, ha a build sikeres volt.
5. **Publish release**.

**Publikálás előtt:** nézd át a `THIRD_PARTY_NOTICES.md` fájlt, és ellenőrizd az eredeti témák, képek és betűkészletek továbbterjesztési feltételeit.
