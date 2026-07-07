# mundwerk

## Aussprache-App für Deutsch Lernende und Lehrende

Unser Ziel ist die Erstellung eines interaktiven Web-Tools zur Erlernung der deutschen Standardaussprache. 

Es soll anschauliche Erklärungen und Übungen zur segmentalen und suprasegmentalen Phonetik beinhalten,
also alle Bereiche vom Einzellaut bis zur Intonation umfassen. 
Das Besondere daran wird sein, dass es sich nicht nur, wie bisher im Online-Angebot, 
um Hör- bzw. Wahrnehmungsübungen handelt, sondern dem Lerner Funktionen zur Korrektur seiner Eigenproduktion bereitstellt. 
Darüber hinaus berücksichtigt die Zusammenstellung der Übungseinheiten die spezifischen Schwierigkeiten des jeweiligen Lerners 
in Bezug auf seine Ausgangssprache.

__Mundwerk__ ist als WebApp konzipiert und mit einem MVC-Framework umgesetzt. Im benutzerfreundlichen und modernen Frontend können Nutzer Audiosequenzen aufnehmen, die an den Server geschickt und dort analysiert werden. Nutzer können sich einloggen, auf ihre History zurückgreifen, in Übungen wieder einsteigen, Übungen wiederholen, Fehlerquoten anzeigen lassen, etc.
Das Backend ist datenbankgestützt. Gespeichert werden die Nutzerdaten und das Expertenwissen. Die hochgeladenen Audiodateien werden von linguistisch-phonetischen OpenSource-Programmen analysiert und verarbeitet. Das korrekte Modell und  die korrigierte Version der Eigenproduktion werden zurückgegeben, sowohl als Audiostream als auch als akustisch/artikulatorisch korrelierte Vektor-Grafik “Mund/Zunge/Öffnung”.
Die Webapp ist lokalisiert (Sprache für die Menüführung und Erklärungen). Die Sprache des Userinterfaces sollte als Vorgabe die Ausgangssprache des Lernenden sein, also kein Hinderungsgrund für die effiziente Nutzung der App darstellen.

