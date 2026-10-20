/**
 * ASALI vs NAKALI - Master PDF & HTML Book Generator
 * Uses Pandoc, MathJax 3 (SVG), Mermaid 10, Prism.js, and Chrome DevTools Protocol.
 */
const { spawn, execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT_DIR = path.resolve(__dirname, '..');
const MD_FILE = path.join(ROOT_DIR, 'ASALI_COMPLETE_SYSTEM_GUIDE.md');
const HTML_FILE = path.join(ROOT_DIR, 'ASALI_COMPLETE_SYSTEM_GUIDE.html');
const PDF_FILE = path.join(ROOT_DIR, 'ASALI_COMPLETE_SYSTEM_GUIDE.pdf');

async function main() {
    console.log('>>> [1/5] Converting Markdown with Pandoc...');
    const rawHtml = execSync(`pandoc "${MD_FILE}" -f markdown -t html --mathjax`, {
        encoding: 'utf8',
        maxBuffer: 10 * 1024 * 1024
    });

    console.log('>>> [2/5] Synthesizing Publication-Grade HTML Template...');
    const fullHtml = buildHtmlTemplate(rawHtml);
    fs.writeFileSync(HTML_FILE, fullHtml, 'utf8');
    console.log(`Saved HTML preview to: ${HTML_FILE} (${fs.statSync(HTML_FILE).size} bytes)`);

    console.log('>>> [3/5] Launching Headless Chrome with CDP...');
    const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', [
        '--headless=new',
        '--remote-debugging-port=9222',
        '--disable-gpu',
        '--no-first-run',
        '--no-default-browser-check'
    ]);

    await new Promise(r => setTimeout(r, 1200));

    try {
        console.log('>>> [4/5] Loading Page and Waiting for Mermaid & MathJax to Render...');
        const newPageResp = await fetch('http://127.0.0.1:9222/json/new?about:blank', { method: 'PUT' });
        const target = await newPageResp.json();
        const ws = new WebSocket(target.webSocketDebuggerUrl);

        await new Promise((resolve, reject) => {
            ws.onopen = resolve;
            ws.onerror = reject;
        });

        let reqId = 1;
        function send(method, params = {}) {
            return new Promise((resolve, reject) => {
                const id = reqId++;
                const timer = setTimeout(() => reject(new Error(`Timeout on ${method}`)), 30000);
                const handler = (evt) => {
                    const data = JSON.parse(evt.data);
                    if (data.id === id) {
                        clearTimeout(timer);
                        ws.removeEventListener('message', handler);
                        if (data.error) reject(data.error);
                        else resolve(data.result);
                    }
                };
                ws.addEventListener('message', handler);
                ws.send(JSON.stringify({ id, method, params }));
            });
        }

        await send('Page.enable');
        await send('Page.navigate', { url: `file://${HTML_FILE}` });

        // Wait for __PDF_READY__ flag
        console.log('Waiting for render completion signal (__PDF_READY__)...');
        let ready = false;
        for (let i = 0; i < 45; i++) {
            await new Promise(r => setTimeout(r, 1000));
            try {
                const evalRes = await send('Runtime.evaluate', { expression: 'window.__PDF_READY__ === true' });
                if (evalRes && evalRes.result && evalRes.result.value === true) {
                    ready = true;
                    console.log(`Render completed successfully after ${i + 1}s!`);
                    break;
                }
            } catch (err) {
                // Ignore transient errors while page is loading
            }
        }

        if (!ready) {
            console.warn('Warning: Timed out waiting for __PDF_READY__, proceeding with print anyway.');
        }

        // Additional settling delay for layout stabilization
        await new Promise(r => setTimeout(r, 1500));

        console.log('>>> [5/5] Generating High-Resolution PDF via Page.printToPDF...');
        const printResult = await send('Page.printToPDF', {
            printBackground: true,
            paperWidth: 8.27,      // Standard A4 width in inches
            paperHeight: 11.69,    // Standard A4 height in inches
            marginTop: 0.65,       // Top margin in inches (~16.5mm)
            marginBottom: 0.65,    // Bottom margin in inches (~16.5mm)
            marginLeft: 0.6,       // Left margin in inches (~15mm)
            marginRight: 0.6,      // Right margin in inches (~15mm)
            displayHeaderFooter: true,
            headerTemplate: `
                <div style="font-family: 'Plus Jakarta Sans', Inter, -apple-system, sans-serif; font-size: 7.5pt; color: #94a3b8; width: 100%; display: flex; justify-content: space-between; padding: 0 16mm; border-bottom: 1px solid #f1f5f9; padding-bottom: 3px;">
                    <span style="font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase;">ASALI (असली) vs NAKALI (नकली) &mdash; Master System &amp; Theory Guide</span>
                    <span style="color: #cbd5e1;">IIA Project 2 Monograph</span>
                </div>
            `,
            footerTemplate: `
                <div style="font-family: 'Plus Jakarta Sans', Inter, -apple-system, sans-serif; font-size: 7.5pt; color: #94a3b8; width: 100%; display: flex; justify-content: space-between; padding: 0 16mm; border-top: 1px solid #f1f5f9; padding-top: 3px;">
                    <span>Confidential &bull; Academic &amp; Regulatory Technical Report</span>
                    <span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
                </div>
            `
        });

        const pdfBuffer = Buffer.from(printResult.data, 'base64');
        fs.writeFileSync(PDF_FILE, pdfBuffer);
        const stats = fs.statSync(PDF_FILE);
        console.log(`=======================================================`);
        console.log(`SUCCESS! Beautiful PDF generated at:`);
        console.log(`${PDF_FILE}`);
        console.log(`File Size: ${(stats.size / 1024).toFixed(1)} KB`);
        console.log(`=======================================================`);

        ws.close();
    } catch (err) {
        console.error('Fatal error during PDF generation:', err);
    } finally {
        chrome.kill();
    }
}

function buildHtmlTemplate(bodyContent) {
    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ASALI vs NAKALI — Master System & Architecture Guide</title>

<!-- Fonts -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:ital,wght@0,400;0,500;0,600;1,400&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap" rel="stylesheet">

<!-- Prism Syntax Highlighting -->
<link href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css" rel="stylesheet" />

<!-- Mermaid JS -->
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>

<!-- MathJax 3 Configuration -->
<script>
window.MathJax = {
  tex: {
    inlineMath: [['\\\\(', '\\\\)'], ['$', '$']],
    displayMath: [['\\\\[', '\\\\]'], ['$$', '$$']]
  },
  svg: {
    fontCache: 'global'
  }
};
</script>
<script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>

<style>
/* CSS Reset & Variables */
:root {
  --primary: #0284c7;
  --primary-dark: #0369a1;
  --primary-light: #e0f2fe;
  --slate-900: #0f172a;
  --slate-800: #1e293b;
  --slate-700: #334155;
  --slate-600: #475569;
  --slate-400: #94a3b8;
  --slate-200: #e2e8f0;
  --slate-100: #f1f5f9;
  --slate-50: #f8fafc;
  --emerald-600: #059669;
  --emerald-50: #ecfdf5;
  --rose-600: #e11d48;
  --rose-50: #fff1f2;
  --amber-600: #d97706;
  --amber-50: #fffbeb;
}

* {
  box-sizing: border-box;
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 10pt;
  line-height: 1.6;
  color: var(--slate-800);
  background: #ffffff;
  margin: 0;
  padding: 0;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
}

/* Print Page Rules */
@page {
  size: A4 portrait;
  margin: 16mm 14mm 16mm 14mm;
}

@media print {
  body {
    font-size: 9.5pt;
    line-height: 1.55;
  }
  .page-break {
    page-break-before: always;
    break-before: always;
  }
  .no-break {
    page-break-inside: avoid;
    break-inside: avoid;
  }
  h1 {
    page-break-before: always;
    break-before: always;
  }
  h1:first-of-type, .cover-page h1 {
    page-break-before: avoid;
    break-before: avoid;
  }
  h1, h2, h3, h4 {
    page-break-after: avoid;
    break-after: avoid;
  }
  table, pre, .mermaid-card, .viva-box, .cover-page {
    page-break-inside: avoid;
    break-inside: avoid;
  }
}

/* Document Container */
.doc-container {
  max-width: 100%;
  margin: 0 auto;
  padding: 0;
}

/* Cover Page Hero */
.cover-page {
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 60%, #0369a1 100%);
  color: #ffffff;
  padding: 44px 38px;
  border-radius: 14px;
  margin-bottom: 32px;
  box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.2);
  page-break-inside: avoid;
  break-inside: avoid;
}

.cover-badge {
  display: inline-block;
  background: rgba(2, 132, 199, 0.35);
  border: 1px solid rgba(56, 189, 248, 0.4);
  color: #7dd3fc;
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 7.5pt;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  padding: 5px 12px;
  border-radius: 9999px;
  margin-bottom: 18px;
}

.cover-title {
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 28pt;
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.15;
  margin: 0 0 12px 0;
  color: #ffffff;
}

.cover-title span {
  color: #38bdf8;
}

.cover-subtitle {
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 13pt;
  font-weight: 500;
  line-height: 1.45;
  color: #94a3b8;
  margin: 0 0 28px 0;
  max-width: 90%;
}

.cover-meta-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
  padding-top: 20px;
}

.cover-meta-item {
  font-size: 8pt;
}

.cover-meta-label {
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
  margin-bottom: 4px;
}

.cover-meta-val {
  color: #e2e8f0;
  font-weight: 600;
  font-size: 8.5pt;
}

/* Headings */
h1 {
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 18pt;
  font-weight: 800;
  color: var(--slate-900);
  letter-spacing: -0.025em;
  margin-top: 36px;
  margin-bottom: 14px;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--slate-100);
}

h2 {
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 13.5pt;
  font-weight: 700;
  color: var(--slate-800);
  letter-spacing: -0.02em;
  margin-top: 24px;
  margin-bottom: 10px;
}

h3 {
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 11.5pt;
  font-weight: 700;
  color: var(--primary-dark);
  margin-top: 18px;
  margin-bottom: 8px;
}

h4 {
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 10pt;
  font-weight: 700;
  color: var(--slate-700);
  margin-top: 14px;
  margin-bottom: 6px;
}

/* Paragraphs & Typography */
p {
  margin-top: 0;
  margin-bottom: 10px;
  color: var(--slate-700);
}

strong {
  color: var(--slate-900);
  font-weight: 600;
}

ul, ol {
  margin-top: 0;
  margin-bottom: 12px;
  padding-left: 20px;
  color: var(--slate-700);
}

li {
  margin-bottom: 4px;
}

hr {
  border: 0;
  height: 1px;
  background: var(--slate-200);
  margin: 28px 0;
}

blockquote {
  border-left: 4px solid var(--primary);
  background: var(--slate-50);
  margin: 14px 0;
  padding: 12px 18px;
  border-radius: 0 8px 8px 0;
  color: var(--slate-700);
  font-style: italic;
}

blockquote p:last-child {
  margin-bottom: 0;
}

/* Inline Code */
code {
  font-family: 'JetBrains Mono', monospace;
  font-size: 8.5pt;
  background: var(--slate-100);
  color: var(--slate-800);
  padding: 2px 5px;
  border-radius: 4px;
  border: 1px solid var(--slate-200);
}

/* Code Blocks */
pre {
  background: #0f172a !important;
  color: #e2e8f0;
  padding: 14px 16px;
  border-radius: 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 8pt;
  line-height: 1.5;
  overflow-x: auto;
  margin: 14px 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  page-break-inside: avoid;
  break-inside: avoid;
}

pre code {
  background: transparent !important;
  border: none !important;
  color: inherit !important;
  padding: 0 !important;
  font-size: inherit !important;
}

/* Tables */
table {
  width: 100%;
  border-collapse: collapse;
  margin: 18px 0;
  font-size: 8.5pt;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  page-break-inside: avoid;
  break-inside: avoid;
}

th {
  background-color: var(--slate-900);
  color: #ffffff;
  text-align: left;
  padding: 8px 12px;
  font-weight: 600;
  font-size: 8pt;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  border-bottom: 1px solid var(--slate-800);
}

td {
  padding: 8px 12px;
  border-bottom: 1px solid var(--slate-200);
  color: var(--slate-700);
  vertical-align: top;
}

tr:nth-child(even) td {
  background-color: var(--slate-50);
}

/* Mermaid Visual Containers */
.mermaid-card {
  background: #ffffff;
  border: 1px solid var(--slate-200);
  border-radius: 10px;
  padding: 18px 16px;
  margin: 18px 0;
  text-align: center;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.03);
  page-break-inside: avoid;
  break-inside: avoid;
}

.mermaid {
  display: flex;
  justify-content: center;
  align-items: center;
  background: transparent;
  font-family: 'Inter', sans-serif !important;
}

.mermaid svg {
  max-width: 100% !important;
  height: auto !important;
}

/* MathJax Formulas */
.mjx-chtml {
  font-size: 105% !important;
}

p .math.display {
  display: block;
  text-align: center;
  margin: 12px 0;
  padding: 10px;
  background: var(--slate-50);
  border-radius: 6px;
  border: 1px solid var(--slate-100);
}

/* Viva Questions Styling */
.viva-box {
  background: #f0f9ff;
  border-left: 4px solid var(--primary);
  border-radius: 0 8px 8px 0;
  padding: 14px 18px;
  margin: 16px 0;
  page-break-inside: avoid;
  break-inside: avoid;
}

.viva-box h4 {
  color: var(--primary-dark);
  margin-top: 0;
  font-size: 10.5pt;
}

/* Table of Contents Styling */
#table-of-contents + ol {
  columns: 2;
  column-gap: 24px;
  background: var(--slate-50);
  border: 1px solid var(--slate-200);
  border-radius: 10px;
  padding: 18px 24px 18px 36px;
  font-size: 9pt;
  margin-bottom: 28px;
}

#table-of-contents + ol li {
  margin-bottom: 6px;
  break-inside: avoid;
}

#table-of-contents + ol a {
  color: var(--slate-800);
  text-decoration: none;
  font-weight: 500;
}

#table-of-contents + ol a:hover {
  color: var(--primary);
  text-decoration: underline;
}
</style>
</head>
<body>

<div class="doc-container">

  <!-- Cover Page Header -->
  <div class="cover-page">
    <div class="cover-badge">INFORMATION INTEGRATION &amp; ARCHITECTURE &bull; TECHNICAL MONOGRAPH</div>
    <h1 class="cover-title">ASALI (असली) <span>vs</span> NAKALI (नकली)</h1>
    <p class="cover-subtitle">The Complete Zero-to-100 Master Architecture, Codebase, Heterogeneous Integration, and Detection Theory Guide</p>
    
    <div class="cover-meta-grid">
      <div class="cover-meta-item">
        <div class="cover-meta-label">Integration Paradigm</div>
        <div class="cover-meta-val">Global-as-View (GAV)</div>
      </div>
      <div class="cover-meta-item">
        <div class="cover-meta-label">Distributed Mesh</div>
        <div class="cover-meta-val">4 Autonomous Silos</div>
      </div>
      <div class="cover-meta-item">
        <div class="cover-meta-label">Detection Logic</div>
        <div class="cover-meta-val">2-Tier Hybrid Architecture</div>
      </div>
      <div class="cover-meta-item">
        <div class="cover-meta-label">Audit Security</div>
        <div class="cover-meta-val">SHA-256 Ledger Chain</div>
      </div>
    </div>
  </div>

  <!-- Main Body Transformed by Pandoc -->
  <div class="content-body">
    ${bodyContent}
  </div>

</div>

<!-- Prism JS -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/autoloader/prism-autoloader.min.js"></script>

<script>
window.__PDF_READY__ = false;

async function prepareAndRender() {
  console.log("Preparing DOM for rendering...");

  // 1. Remove duplicate H1 and H2 rendered by pandoc right after cover
  const firstH1 = document.querySelector('.content-body > h1:first-of-type');
  if (firstH1 && firstH1.textContent.includes('ASALI')) {
    firstH1.style.display = 'none';
    const firstH2 = firstH1.nextElementSibling;
    if (firstH2 && firstH2.tagName === 'H2') firstH2.style.display = 'none';
    const hr = firstH2 ? firstH2.nextElementSibling : null;
    if (hr && hr.tagName === 'HR') hr.style.display = 'none';
  }

  // 2. Transform pre.mermaid to div.mermaid wrapped in card
  document.querySelectorAll('pre.mermaid').forEach((pre) => {
    const codeEl = pre.querySelector('code');
    const rawText = codeEl ? codeEl.textContent : pre.textContent;
    
    const card = document.createElement('div');
    card.className = 'mermaid-card';
    
    const div = document.createElement('div');
    div.className = 'mermaid';
    div.textContent = rawText;
    
    card.appendChild(div);
    pre.parentNode.replaceChild(card, pre);
  });

  // 3. Wrap Q1-Q5 Viva in styled cards
  document.querySelectorAll('h4').forEach(h4 => {
    if (h4.textContent.startsWith('Q1:') || h4.textContent.startsWith('Q2:') || 
        h4.textContent.startsWith('Q3:') || h4.textContent.startsWith('Q4:') || 
        h4.textContent.startsWith('Q5:')) {
      const nextUl = h4.nextElementSibling;
      if (nextUl && nextUl.tagName === 'UL') {
        const wrapper = document.createElement('div');
        wrapper.className = 'viva-box';
        h4.parentNode.insertBefore(wrapper, h4);
        wrapper.appendChild(h4);
        wrapper.appendChild(nextUl);
      }
    }
  });

  // 4. Initialize Mermaid with publication palette
  mermaid.initialize({
    startOnLoad: false,
    theme: 'base',
    themeVariables: {
      primaryColor: '#e0f2fe',
      primaryTextColor: '#0369a1',
      primaryBorderColor: '#0284c7',
      lineColor: '#64748b',
      secondaryColor: '#f1f5f9',
      tertiaryColor: '#f8fafc',
      fontFamily: 'Inter, sans-serif',
      fontSize: '13px'
    },
    flowchart: { curve: 'basis', htmlLabels: true, useMaxWidth: true }
  });

  // 5. Run Mermaid
  console.log("Running Mermaid diagrams...");
  try {
    await mermaid.run();
  } catch (err) {
    console.error("Mermaid error:", err);
  }

  // 6. Typeset MathJax
  console.log("Typesetting MathJax...");
  if (window.MathJax && window.MathJax.typesetPromise) {
    try {
      await window.MathJax.typesetPromise();
    } catch (err) {
      console.error("MathJax error:", err);
    }
  }

  // 7. Highlight code blocks with Prism
  if (window.Prism) {
    window.Prism.highlightAll();
  }

  // 8. Signal readiness
  setTimeout(() => {
    window.__PDF_READY__ = true;
    console.log("ALL RENDER PHASES COMPLETED! Ready for Chrome PDF engine.");
  }, 1000);
}

window.addEventListener('DOMContentLoaded', prepareAndRender);
</script>

</body>
</html>`;
}

main();
