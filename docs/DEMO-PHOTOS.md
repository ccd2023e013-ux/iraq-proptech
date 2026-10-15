# Representative photos for DEMO listings

DEMO listings are fictional. Their photos are **representative**: real, openly
licensed photographs of the *kind* of street or building, never of the listed
property. Every one is captioned that way on the image, in the gallery caption
and on `/credits`, and the property page states it in its "What you can rely
on" panel.

## Sources evaluated (October 2026)

The library holds 13 photos: 11 from Commons and 2 from Flickr via Openverse.


| Source | Licence | Key needed | Iraqi residential coverage | Verdict |
| --- | --- | --- | --- | --- |
| **Wikimedia Commons** | Public domain, CC0, CC BY, CC BY-SA (checked per file by the API) | No | Thin. A 352-candidate survey of Iraqi streets, neighbourhoods and housing categories is exhausted: 11 accepted, the rest are already used, heritage sites, war damage, people, or mis-located (e.g. Pakistan's "Zubair"). | In use (automated, licence-checked). |
| **Openverse** (CC search over Flickr and others) | Per image; we accept CC0, PDM, BY, BY-SA only | No for light use: anonymous requests must keep `page_size` ≤ 20 and about one request per second (larger pages → HTTP 401, faster → HTTP 429). A free registered key raises the limits. | 87 licence-clean candidates in the first survey, mostly shrines, people, press and non-Iraq photos; 2 accepted (a Diyala villa, a Baghdad residential rooftop view). | In use (automated, licence-checked). |
| **Unsplash** | Unsplash License: free commercial use, no attribution required; may not be compiled into a similar or competing service | API key for automation (free); manual download needs none | Very few Iraqi homes; some Erbil/Baghdad streetscapes | Manual only, sparingly. |
| **Pexels / Pixabay** | Own free licences (commercial use, no attribution); no model or property releases — identifiable people and trademarks are the user's risk | Free key for API; manual download needs none | Sparse for Iraq | Manual only, sparingly. |
| **Owner's own photography** | Owned outright | — | Exactly the right content | Best long-term source. |

We credit every photo even where the licence does not require it, and the
caption names the source.

## Acceptance rules (apply to every source)

1. **Licence** is one of the above, and is recorded with the author and a link to the source page.
2. **No people as subject**, no readable licence plates or faces, no portraits or posters of real public figures (religious or political).
3. **No heritage monuments, palaces, government buildings, embassies, military sites, war damage, or shrines.** These would mislead as "properties" and carry associations a listing must not.
4. **Iraq only**, verified from the file's own description (names like "Zubair" also exist elsewhere).
5. **Landscape**, at least 1000 px wide, in focus, daylight; no heavy dust storm or photographer's shadow.
6. **One photo per composition**: no two cards in one view show the same photo (the home page already prefers one listing per property type).

## Automated process (Commons and Openverse)

1. Edit `scripts/demo_photos/request.txt` on the design branch, with `survey` (Commons) or `openverse` on the first line, and push.
   - The *Demo photos* workflow writes numbered contact sheets, `candidates.json` and `log.txt` to a new `assets/demo-photos-<run>` branch.
2. Review the sheets against the rules above. Open each candidate at full size before accepting it: a contact-sheet thumbnail hid the portrait poster in the last rejected one.
3. Put `fetch` on the first line of `request.txt`, then one `KIND|File:Title` line (Commons) or `KIND|openverse:<id>` line (Openverse) per accepted photo, and push.
   - The workflow re-checks each licence, resizes to 1600 px, strips EXIF and GPS data, and writes the photos with a `manifest.json` holding title, author, licence, licence URL and source page.
4. Copy the new files into `backend/app/demo_photos/`, number them after the existing ones (e.g. `apartment-17.jpg`), and append their manifest entries.
5. Re-seed the preview. `demo_images.pick_photo` draws by property type.

## Manual process (Unsplash, Pexels, Pixabay, owner photos)

1. Download the largest size from the photo's own page and save that page's URL.
2. Resize to 1600 px on the long edge and strip all metadata, for example with `exiftool -all= file.jpg`.
3. Add a manifest entry. `licence` is the licence name ("Unsplash License", "Pexels License"), `licence_url` is the licence page, `author` is the photographer as shown, and `source` is the photo page.
4. The caption names the source from the `source` URL (`demo_images.source_name`): Wikimedia Commons and Flickr are recognised. For any other site, it shows the host name. Add a readable name there when a new source is used.
