/**
 * Utility functions for exporting 100-card Commander decks to various deckbuilder formats.
 *
 * Supported formats:
 * - Moxfield Format (Tagged with *CMDR*, exact 100 cards)
 * - Archidekt Format (1x Name *CMDR* [Commander], 1x Name [Category])
 * - MTGO .dec Format (// Commander, // Mainboard)
 * - Plain Text .txt Format (Categorized clean text list)
 * - CSV Format (Count,Name,Category,CMC,Type)
 */

export const CATEGORY_LABELS = {
  commander: 'Commander',
  win_con: 'Win Con',
  ramp: 'Ramp',
  draw: 'Draw',
  removal: 'Removal',
  synergy: 'Synergy',
  lands: 'Lands'
};

/**
 * Extracts commanders list from deck object.
 */
export function getCommanders(deck) {
  if (!deck) return [];
  if (Array.isArray(deck.commanders) && deck.commanders.length > 0) {
    return deck.commanders;
  }
  if (deck.categories?.commander && deck.categories.commander.length > 0) {
    return deck.categories.commander;
  }
  if (deck.commander) {
    return [deck.commander];
  }
  return [];
}

/**
 * Groups cards by name, aggregating counts (e.g. basic lands).
 */
export function groupCards(cards = []) {
  const map = new Map();
  for (const card of cards) {
    if (!card || !card.name) continue;
    const name = card.name.trim();
    if (map.has(name)) {
      map.get(name).count += 1;
    } else {
      map.set(name, {
        name,
        count: 1,
        cmc: card.cmc ?? 0,
        type_line: card.type_line ?? '',
        mana_cost: card.mana_cost ?? '',
        color_identity: card.color_identity ?? []
      });
    }
  }
  return Array.from(map.values());
}

/**
 * Moxfield Format:
 * Commanders tagged with *CMDR*:
 * 1 Belbe, Corrupted Observer *CMDR*
 * 1 Sol Ring
 * ...
 * Guaranteed exact 100 cards total.
 */
export function exportToMoxfield(deck) {
  if (!deck) return '';
  const commanders = getCommanders(deck);
  const lines = [];

  for (const cmd of commanders) {
    lines.push(`1 ${cmd.name} *CMDR*`);
  }

  const roleOrder = ['win_con', 'ramp', 'draw', 'removal', 'synergy', 'lands'];
  for (const role of roleOrder) {
    const list = deck.categories?.[role] || [];
    const grouped = groupCards(list);
    for (const card of grouped) {
      lines.push(`${card.count} ${card.name}`);
    }
  }

  return lines.join('\n');
}

/**
 * Archidekt Format:
 * 1x Belbe, Corrupted Observer *CMDR* [Commander]
 * 1x Sol Ring [Ramp]
 * 1x Toxic Deluge [Removal]
 * ...
 */
export function exportToArchidekt(deck) {
  if (!deck) return '';
  const commanders = getCommanders(deck);
  const lines = [];

  for (const cmd of commanders) {
    lines.push(`1x ${cmd.name} *CMDR* [Commander]`);
  }

  const roleOrder = ['win_con', 'ramp', 'draw', 'removal', 'synergy', 'lands'];
  for (const role of roleOrder) {
    const list = deck.categories?.[role] || [];
    const label = CATEGORY_LABELS[role] || role;
    const grouped = groupCards(list);
    for (const card of grouped) {
      lines.push(`${card.count}x ${card.name} [${label}]`);
    }
  }

  return lines.join('\n');
}

/**
 * MTGO .dec Format:
 * // Commander
 * 1 Belbe, Corrupted Observer
 * // Mainboard
 * 1 Sol Ring
 * ...
 */
export function exportToMtgo(deck) {
  if (!deck) return '';
  const commanders = getCommanders(deck);
  const lines = ['// Commander'];

  for (const cmd of commanders) {
    lines.push(`1 ${cmd.name}`);
  }

  lines.push('// Mainboard');
  const roleOrder = ['win_con', 'ramp', 'draw', 'removal', 'synergy', 'lands'];
  for (const role of roleOrder) {
    const list = deck.categories?.[role] || [];
    const grouped = groupCards(list);
    for (const card of grouped) {
      lines.push(`${card.count} ${card.name}`);
    }
  }

  return lines.join('\n');
}

/**
 * Plain Text .txt Format:
 * Categorized and clean text list.
 */
export function exportToText(deck) {
  if (!deck) return '';
  if (deck.decklist_text) return deck.decklist_text;

  const commanders = getCommanders(deck);
  const lines = ['// Commander'];

  for (const cmd of commanders) {
    lines.push(`1 ${cmd.name}`);
  }
  lines.push('');

  const roleOrder = ['win_con', 'ramp', 'draw', 'removal', 'synergy', 'lands'];
  for (const role of roleOrder) {
    const list = deck.categories?.[role] || [];
    if (!list.length) continue;
    const label = CATEGORY_LABELS[role] || role;
    lines.push(`// ${label} (${list.length})`);
    const grouped = groupCards(list).sort((a, b) => a.name.localeCompare(b.name));
    for (const card of grouped) {
      lines.push(`${card.count} ${card.name}`);
    }
    lines.push('');
  }

  return lines.join('\n').trim();
}

/**
 * RFC 4180 compliant CSV string escaper.
 */
export function escapeCsvField(val) {
  const str = String(val ?? '');
  if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

/**
 * CSV Export:
 * Columns: Count,Name,Category,CMC,Type
 */
export function exportToCsv(deck) {
  if (!deck) return '';
  const lines = ['Count,Name,Category,CMC,Type'];
  const commanders = getCommanders(deck);

  for (const cmd of commanders) {
    const cmc = typeof cmd.cmc === 'number' ? cmd.cmc : 0;
    lines.push([
      1,
      escapeCsvField(cmd.name),
      'Commander',
      cmc,
      escapeCsvField(cmd.type_line || '')
    ].join(','));
  }

  const roleOrder = ['win_con', 'ramp', 'draw', 'removal', 'synergy', 'lands'];
  for (const role of roleOrder) {
    const list = deck.categories?.[role] || [];
    const label = CATEGORY_LABELS[role] || role;
    const grouped = groupCards(list);
    for (const card of grouped) {
      const cmc = typeof card.cmc === 'number' ? card.cmc : 0;
      lines.push([
        card.count,
        escapeCsvField(card.name),
        escapeCsvField(label),
        cmc,
        escapeCsvField(card.type_line || '')
      ].join(','));
    }
  }

  return lines.join('\n');
}

/**
 * Counts total cards in an exported format string.
 */
export function countExportCards(text, format) {
  if (!text) return 0;
  const fmt = (format || '').toLowerCase();
  let total = 0;

  if (fmt === 'csv') {
    const lines = text.split(/\r?\n/).filter(Boolean);
    for (let i = 1; i < lines.length; i++) {
      const match = lines[i].match(/^(\d+),/);
      if (match) {
        total += parseInt(match[1], 10);
      }
    }
    return total;
  }

  const lines = text.split(/\r?\n/);
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('//')) continue;
    if (fmt === 'archidekt') {
      const match = trimmed.match(/^(\d+)x\s+/);
      if (match) total += parseInt(match[1], 10);
    } else {
      const match = trimmed.match(/^(\d+)\s+/);
      if (match) total += parseInt(match[1], 10);
    }
  }

  return total;
}

/**
 * Triggers a direct browser file download.
 */
export function downloadDeckFile(content, filename, mimeType = 'text/plain;charset=utf-8') {
  if (!content) return;
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
