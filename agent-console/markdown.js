// Tiny markdown-lite renderer for ADA's draft output, reasoning, and chat
// replies (see app.js). Not a full CommonMark implementation — just the
// subset ADA's system prompt actually produces: headings, bold/italic, inline
// code, links, ordered/unordered/checklist lists, blockquotes, tables, code
// blocks, horizontal rules, and paragraphs.
//
// Mermaid: a ```mermaid fenced block is NOT rendered inline (mermaid.render()
// is async and needs a real DOM node/id, which renderMarkdown()'s pure
// string-building pass doesn't have). Instead it emits a placeholder
// container; call renderMermaidDiagrams(container) after inserting the HTML
// into the DOM to fill placeholders in with rendered SVG. If the mermaid
// library isn't loaded, or a given diagram fails to render, the raw source
// stays readable — never silently dropped.

let mermaidInitialized = false;
let mermaidCounter = 0;

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderInline(value) {
  const codeSpans = [];
  let text = escapeHtml(value).replace(/`([^`\n]+)`/g, (_, code) => {
    const token = `~~CS~~CODE${codeSpans.length}~~CS~~`;
    codeSpans.push(`<code>${code}</code>`);
    return token;
  });

  text = text
    .replace(/\[([^\]]+)]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
    .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
    .replace(/__([^_\n]+)__/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");

  return text.replace(/~~CS~~CODE(\d+)~~CS~~/g, (_, index) => codeSpans[Number(index)]);
}

function tableCells(line) {
  let normalized = line.trim();
  if (normalized.startsWith("|")) normalized = normalized.slice(1);
  if (normalized.endsWith("|")) normalized = normalized.slice(0, -1);
  return normalized.split("|").map((cell) => cell.trim());
}

function isTableSeparatorRow(line) {
  if (!line || !line.includes("-")) return false;
  const cells = tableCells(line);
  return cells.length > 0 && cells.every((cell) => /^:?-+:?$/.test(cell));
}

function cellAlignment(separatorCell) {
  const left = separatorCell.startsWith(":");
  const right = separatorCell.endsWith(":");
  if (left && right) return "center";
  if (right) return "right";
  if (left) return "left";
  return null;
}

function mermaidPlaceholder(code) {
  mermaidCounter += 1;
  const id = `mermaid-${mermaidCounter}-${Math.random().toString(36).slice(2, 8)}`;
  return (
    `<div class="mermaid-diagram" data-mermaid-id="${id}">` +
    `<p class="mermaid-status">Rendering diagram…</p>` +
    `<pre class="mermaid-source" hidden>${escapeHtml(code)}</pre>` +
    `</div>`
  );
}

function codeBlockHtml(language, code) {
  const label = language ? escapeHtml(language) : "text";
  return `<div class="code-block"><span>${label}</span><pre><code>${escapeHtml(code)}</code></pre></div>`;
}

const BLOCK_BOUNDARY = /^(```|#{1,6}\s|\s*>\s?|\s*[-*]\s+|\s*\d+[.)]\s+|\s*(-{3,}|\*{3,}|_{3,})\s*$)/;

export function renderMarkdown(source) {
  const lines = String(source ?? "").replace(/\r\n/g, "\n").split("\n");
  const output = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];

    // Fenced code block — ``` or ```language
    const fence = line.match(/^```\s*([\w-]*)\s*$/);
    if (fence) {
      const language = fence[1] || "";
      const code = [];
      index += 1;
      while (index < lines.length && !/^```\s*$/.test(lines[index])) {
        code.push(lines[index]);
        index += 1;
      }
      index += 1; // skip the closing fence, if there was one
      const raw = code.join("\n");
      output.push(language.toLowerCase() === "mermaid" ? mermaidPlaceholder(raw) : codeBlockHtml(language, raw));
      continue;
    }

    // Heading
    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      const level = heading[1].length;
      output.push(`<h${level}>${renderInline(heading[2].trim())}</h${level}>`);
      index += 1;
      continue;
    }

    // Horizontal rule (and not a blank line)
    if (line.trim() !== "" && /^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
      output.push("<hr>");
      index += 1;
      continue;
    }

    // Blockquote
    if (/^\s*>\s?/.test(line)) {
      const quote = [];
      while (index < lines.length && /^\s*>\s?/.test(lines[index])) {
        quote.push(lines[index].replace(/^\s*>\s?/, ""));
        index += 1;
      }
      output.push(`<blockquote>${quote.map((l) => `<p>${renderInline(l)}</p>`).join("")}</blockquote>`);
      continue;
    }

    // Table — a row containing "|" immediately followed by a separator row
    if (line.includes("|") && isTableSeparatorRow(lines[index + 1])) {
      const headers = tableCells(line);
      const aligns = tableCells(lines[index + 1]).map(cellAlignment);
      index += 2;
      const rows = [];
      while (index < lines.length && lines[index].trim() !== "" && lines[index].includes("|")) {
        rows.push(tableCells(lines[index]));
        index += 1;
      }
      const alignAttr = (i) => (aligns[i] ? ` style="text-align:${aligns[i]}"` : "");
      const thead = `<tr>${headers.map((h, i) => `<th${alignAttr(i)}>${renderInline(h)}</th>`).join("")}</tr>`;
      const tbody = rows
        .map((row) => `<tr>${headers.map((_, i) => `<td${alignAttr(i)}>${renderInline(row[i] ?? "")}</td>`).join("")}</tr>`)
        .join("");
      output.push(`<div class="table-scroll"><table><thead>${thead}</thead><tbody>${tbody}</tbody></table></div>`);
      continue;
    }

    // Checklist / unordered / ordered lists
    const isOrderedLine = /^\s*\d+[.)]\s+/.test(line);
    const isBulletLine = /^\s*[-*]\s+/.test(line);
    if (isOrderedLine || isBulletLine) {
      const ordered = isOrderedLine;
      const items = [];
      while (index < lines.length) {
        const l = lines[index];
        const checklistMatch = !ordered && l.match(/^\s*[-*]\s+\[([ xX])]\s+(.*)$/);
        const bulletMatch = !ordered && !checklistMatch && l.match(/^\s*[-*]\s+(.+)$/);
        const orderedMatch = ordered && l.match(/^\s*\d+[.)]\s+(.+)$/);
        if (checklistMatch) {
          items.push({ checked: checklistMatch[1].toLowerCase() === "x", text: checklistMatch[2] });
        } else if (bulletMatch) {
          items.push({ text: bulletMatch[1] });
        } else if (orderedMatch) {
          items.push({ text: orderedMatch[1] });
        } else {
          break;
        }
        index += 1;
      }
      const itemsHtml = items
        .map((item) =>
          item.checked !== undefined
            ? `<li class="check-item"><span class="check-mark${item.checked ? " checked" : ""}">${item.checked ? "✓" : ""}</span><span>${renderInline(item.text)}</span></li>`
            : `<li>${renderInline(item.text)}</li>`
        )
        .join("");
      output.push(ordered ? `<ol>${itemsHtml}</ol>` : `<ul>${itemsHtml}</ul>`);
      continue;
    }

    // Blank line
    if (line.trim() === "") {
      index += 1;
      continue;
    }

    // Paragraph — gather consecutive lines until the next block-level element
    const paragraph = [line.trim()];
    index += 1;
    while (index < lines.length && lines[index].trim() !== "" && !BLOCK_BOUNDARY.test(lines[index])) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    output.push(`<p>${renderInline(paragraph.join(" "))}</p>`);
  }

  return output.join("\n");
}

function ensureMermaidInitialized() {
  if (mermaidInitialized || !window.mermaid) return;
  window.mermaid.initialize({
    startOnLoad: false,
    theme: "neutral",
    securityLevel: "strict",
    flowchart: { htmlLabels: true },
  });
  mermaidInitialized = true;
}

/** Fill in every `.mermaid-diagram` placeholder inside `container` with a
 * rendered SVG. Safe to call repeatedly / on containers with none. Never
 * throws — a diagram that fails to render falls back to its readable source
 * rather than taking down the rest of the page. */
export async function renderMermaidDiagrams(container) {
  if (!container) return;
  const diagrams = [...container.querySelectorAll(".mermaid-diagram:not(.mermaid-rendered):not(.mermaid-error)")];
  if (!diagrams.length) return;

  if (!window.mermaid) {
    for (const figure of diagrams) {
      const status = figure.querySelector(".mermaid-status");
      const source = figure.querySelector(".mermaid-source");
      if (status) status.textContent = "Diagram library not available — showing source below.";
      if (source) source.hidden = false;
    }
    return;
  }

  ensureMermaidInitialized();

  for (const figure of diagrams) {
    const source = figure.querySelector(".mermaid-source");
    const code = source ? source.textContent : "";
    const id = figure.dataset.mermaidId || `mermaid-${Math.random().toString(36).slice(2, 10)}`;
    try {
      const { svg } = await window.mermaid.render(`${id}-svg`, code);
      figure.classList.add("mermaid-rendered");
      figure.innerHTML = svg;
    } catch {
      figure.classList.add("mermaid-error");
      figure.innerHTML =
        `<p class="mermaid-status">Could not render this diagram.</p>` +
        `<details><summary>Diagram source</summary><pre>${escapeHtml(code)}</pre></details>`;
    }
  }
}
