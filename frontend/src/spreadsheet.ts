export function parseSpreadsheetGrid(text: string): string[][] {
  const normalized = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const rows = normalized.split("\n").map((row) => (row.includes("\t") ? row.split("\t") : parseCsvRow(row)));
  while (rows.length > 0 && rows[rows.length - 1].every((cell) => cell.trim() === "")) {
    rows.pop();
  }
  return rows.filter((row) => row.some((cell) => cell.trim() !== ""));
}

function parseCsvRow(row: string) {
  const cells: string[] = [];
  let current = "";
  let quoted = false;

  for (let index = 0; index < row.length; index += 1) {
    const char = row[index];
    const next = row[index + 1];
    if (char === '"' && quoted && next === '"') {
      current += '"';
      index += 1;
      continue;
    }
    if (char === '"') {
      quoted = !quoted;
      continue;
    }
    if (char === "," && !quoted) {
      cells.push(current);
      current = "";
      continue;
    }
    current += char;
  }
  cells.push(current);
  return cells;
}
