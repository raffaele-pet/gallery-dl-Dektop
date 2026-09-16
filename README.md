# Gallery-DL Windows GUI

Incolla il link, scegli dove salvare e premi **Scarica**. Nessun menu di configurazione, nessun cookie da esportare a mano.

## Installazione

Su Windows 10/11 esegui `INSTALL.bat`, poi avvia `RUN.vbs` (o il collegamento Gallery-DL sul Desktop). A ogni esecuzione l’installer confronta le versioni presenti con le ultime release stabili disponibili e aggiorna automaticamente gallery-dl, yt-dlp e le relative dipendenze. Prepara inoltre Python e FFmpeg in un ambiente isolato. Per le pagine dinamiche usa Google Chrome, Microsoft Edge o Brave già installato nel sistema: non scarica una seconda copia di Chromium. `RUN_DEBUG.cmd` mostra eventuali problemi di avvio.

## Uso

1. Incolla uno o più link nel campo in alto: sono accettati anche link Markdown copiati da una chat.
2. **Salva in** è la base portabile `Downloads\gallery-dl`; un percorso relativo parte dalla cartella utente. **Cartella** viene proposta dal dominio e dal percorso del primo link e resta modificabile.
3. Premi **Scarica**. **Apri cartella** mostra il risultato; **Annulla** interrompe il lavoro senza rimuovere i file completati.

**Aggiorna** aggiorna gallery-dl e yt-dlp. Dopo un aggiornamento del progetto, esegui nuovamente `INSTALL.bat` per allineare tutte le dipendenze. L’installer rimuove anche l’eventuale vecchia cartella `.browser-binaries`, che non serve più.

La finestra avviata da `RUN.vbs` e il collegamento sul Desktop usano l’[icona fornita da Icons8](https://img.icons8.com/?size=100&id=mRzzo2KBnP3n&format=png&color=000000).

## Come funziona

- Gallerie, post e profili riconosciuti: estrattori dedicati di [gallery-dl](https://github.com/mikf/gallery-dl). È richiesta almeno la versione [1.32.12](https://github.com/mikf/gallery-dl/releases/tag/v1.32.12), che corregge gli estrattori Instagram `posts` e `reels` rotti nella 1.32.11. Non è più necessario leggere la griglia e ripetere ogni post singolarmente.
- Pagine web comuni, come una homepage o un articolo: lettura delle immagini HTML, lazy-loading, srcset, metadati e immagini strutturate. Viene scelta la variante responsive più grande dichiarata. Se l’HTML non contiene immagini, viene tentata la pagina renderizzata con il browser Chromium già installato.
- Le immagini delle pagine normali vengono verificate prima del salvataggio; i piccoli elementi inferiori a 64 pixel per lato sono ignorati. I duplicati identici nella stessa pagina vengono saltati. Un link diretto conserva anche le immagini piccole.
- Ogni operazione usa la sottocartella mostrata nel campo **Cartella**: per esempio `www.repubblica.it`, `www.repubblica.it-sport` o `www.instagram.com-raffaele.pet`. Incollando più link viene usato il nome ricavato dal primo.
- Ripetere lo stesso download riutilizza la cartella: le pagine comuni deduplicano in base al contenuto e gallery-dl salta i file già presenti. Non viene aggiunto un orario, perché produrrebbe copie identiche a ogni esecuzione.

Una homepage scarica le immagini contenute in quella pagina, **non tutti gli articoli dell’intero sito**. Il browser automatico esegue uno scorrimento limitato, non una scansione infinita. Non sono garantite tutte le immagini caricate dinamicamente, gli SVG o i contenuti dietro blocchi di accesso.

## Accesso ai siti

Non vengono richiesti file cookie, password nell’app o modifiche alla sicurezza del browser. Per Instagram l’app prova prima a leggere in memoria soltanto i cookie Instagram dal browser installato. Chrome può impedirlo mentre è aperto o per le proprie protezioni dei cookie; in quel caso l’app apre lo stesso browser installato con un profilo controllato e separato. Effettua lì l’accesso una sola volta: la sessione viene riutilizzata automaticamente e resta nella cartella locale `.browser-profile`, esclusa da Git. Non condividere questa cartella: contiene dati di sessione sensibili. Il download riparte quando il login viene rilevato; l’attesa massima è 5 minuti.

Il profilo separato è intenzionale: riutilizzare direttamente il profilo personale di Chrome mentre è aperto è spesso bloccato da Windows/Chrome e forzarne l’uso rischierebbe di danneggiare il profilo. Viene riusato il programma Chrome già presente, non viene installato un altro browser.

Questo non elimina le restrizioni imposte da Instagram: login, verifica dell’account, contenuti privati, limiti e cambiamenti del sito possono ancora impedire l’estrazione. Gli altri siti con autenticazione obbligatoria possono richiedere un’integrazione specifica. Nessuna promessa di scaricare qualsiasi URL.

## Verifica tecnica

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

I test coprono il link Markdown di Repubblica, estrazione HTML, download HTTP reale locale, immagini non valide, duplicati, risultati parziali, messaggi del processo, sessioni Instagram e rendering JavaScript. Chrome, Edge o Brave deve essere installato nel sistema.

Interfaccia non ufficiale, licenza MIT. Il logo originale e la palette sono quelli richiesti per il progetto; gallery-dl rimane un progetto indipendente. Scarica solo contenuti che sei autorizzato a salvare e rispetta le condizioni dei siti.
