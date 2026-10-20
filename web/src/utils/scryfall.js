/**
 * Fetches card metadata in batches from Scryfall's Collection lookup endpoint.
 * Respects rate limits and splits list into chunks of 75.
 * 
 * @param {string[]} cardNames List of card names
 * @returns {Promise<Object>} Map of lowercase card names to card metadata objects
 */
export async function fetchCardsMetadata(cardNames) {
  const uniqueNames = [...new Set(cardNames.map(name => name.trim().toLowerCase()))].filter(Boolean);
  if (uniqueNames.length === 0) return {};

  const chunks = [];
  const chunkSize = 75;
  for (let i = 0; i < uniqueNames.length; i += chunkSize) {
    chunks.push(uniqueNames.slice(i, i + chunkSize));
  }

  const database = {};

  for (const chunk of chunks) {
    const body = {
      identifiers: chunk.map(name => ({ name }))
    };

    try {
      const response = await fetch("https://api.scryfall.com/cards/collection", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json;q=0.9,*/*;q=0.8"
        },
        body: JSON.stringify(body)
      });

      if (!response.ok) {
        throw new Error(`Scryfall API error: ${response.status}`);
      }

      const data = await response.json();
      
      if (data && data.not_found && data.not_found.length > 0) {
        console.warn("Cards not found on Scryfall in chunk lookup:", data.not_found);
      }
      
      if (data && Array.isArray(data.data)) {
        for (const card of data.data) {
          const name = card.name;
          if (!name) continue;

          const faces = Array.isArray(card.card_faces) ? card.card_faces : [];

          // 1. Resolve oracle_text (combine faces if root is empty, as in DFCs/MDFCs)
          let oracleText = card.oracle_text || "";
          if (!oracleText && faces.length > 0) {
            oracleText = faces.map(f => f.oracle_text || "").filter(Boolean).join("\n//\n");
          }

          // 2. Resolve mana_cost (take front face if root is empty)
          let manaCost = card.mana_cost || "";
          if (!manaCost && faces.length > 0) {
            manaCost = faces[0].mana_cost || "";
          }

          // 3. Resolve type_line and parse types/subtypes across all faces
          let typeLine = card.type_line || "";
          if (!typeLine && faces.length > 0) {
            typeLine = faces.map(f => f.type_line || "").filter(Boolean).join(" // ");
          }

          let types = [];
          let subtypes = [];
          if (typeLine) {
            const faceTypeLines = typeLine.split("//");
            for (const ftl of faceTypeLines) {
              const parts = ftl.split("—");
              const mainTypes = parts[0].trim().split(/\s+/).map(t => t.toLowerCase());
              types.push(...mainTypes);
              if (parts[1]) {
                const subTypes = parts[1].trim().split(/\s+/).filter(Boolean).map(s => s.toLowerCase());
                subtypes.push(...subTypes);
              }
            }
            types = [...new Set(types)];
            subtypes = [...new Set(subtypes)];
          }

          // 4. Resolve image_url (check front face if root image_uris is missing)
          let imageUrl = "";
          if (card.image_uris) {
            imageUrl = card.image_uris.normal || card.image_uris.small || "";
          } else if (faces.length > 0 && faces[0].image_uris) {
            imageUrl = faces[0].image_uris.normal || faces[0].image_uris.small || "";
          }

          // 5. Resolve colors
          let colors = card.colors || [];
          if (colors.length === 0 && faces.length > 0) {
            const combined = new Set();
            for (const f of faces) {
              for (const c of (f.colors || [])) combined.add(c);
            }
            colors = [...combined];
          }

          const cardData = {
            name: name,
            raw_type: typeLine,
            types: types,
            subtypes: subtypes,
            oracle_text: oracleText,
            mana_cost: manaCost,
            cmc: card.cmc ?? 0,
            colors: colors,
            set: card.set || "",
            image_url: imageUrl,
            edhrec_rank: card.edhrec_rank
          };

          // Store by full canonical name
          database[name.toLowerCase()] = cardData;

          // If the card is a split, DFC, or adventure card, alias the front face name
          if (name.includes(" // ")) {
            const frontName = name.split(" // ")[0].trim().toLowerCase();
            if (!database[frontName]) {
              database[frontName] = cardData;
            }
          }
        }
      }
      
      // Delay to respect Scryfall rate limit recommendations (600ms between calls)
      if (chunks.length > 1) {
        await new Promise(resolve => setTimeout(resolve, 600));
      }
    } catch (error) {
      console.error("Error fetching Scryfall data chunk:", error);
    }
  }

  return database;
}
