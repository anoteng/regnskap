# PWA Ikoner

For å få PWA-appen til å fungere optimalt, lag følgende ikoner:

## Påkrevde ikoner:
- `icon-192.png` - 192x192 pixels
- `icon-512.png` - 512x512 pixels

## Hvordan lage ikoner:

1. Design et enkelt ikon (f.eks. 📎 symbol med "R" for Regnskap)
2. Bruk et verktøy som:
   - https://realfavicongenerator.net/ (automatisk generering)
   - Figma/Canva/Photoshop (manuell design)
3. Eksporter som PNG i størrelsene over
4. Plasser filene i denne mappen

## Midlertidig løsning:

Du kan bruke ImageMagick til å lage enkle placeholder-ikoner:

```bash
# Installer ImageMagick først (hvis ikke installert)
sudo apt-get install imagemagick

# Lag 192x192 ikon
convert -size 192x192 xc:#2563eb -gravity center -pointsize 120 -fill white -annotate +0+0 "📎" icon-192.png

# Lag 512x512 ikon
convert -size 512x512 xc:#2563eb -gravity center -pointsize 320 -fill white -annotate +0+0 "📎" icon-512.png
```
