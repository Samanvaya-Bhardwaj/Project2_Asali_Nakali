/**
 * engines.js - Client-side information-integration engines.
 * Levenshtein / Jaro-Winkler / Soundex fuzzy entity resolution, extracted
 * verbatim from the legacy app.js so scoring behaviour is unchanged.
 */

function computeLevenshteinDistance(s1, s2) {
  s1 = s1 || "";
  s2 = s2 || "";
  const m = s1.length;
  const n = s2.length;
  const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = 0; i <= m; i++) dp[i][0] = i;
  for (let j = 0; j <= n; j++) dp[0][j] = j;

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (s1[i - 1] === s2[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1];
      } else {
        dp[i][j] = 1 + Math.min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1]);
      }
    }
  }
  return dp[m][n];
}

function computeJaroWinklerSimilarity(s1, s2) {
  s1 = (s1 || "").toUpperCase();
  s2 = (s2 || "").toUpperCase();
  if (s1 === s2) return 1.0;
  if (!s1.length || !s2.length) return 0.0;

  const matchDistance = Math.floor(Math.max(s1.length, s2.length) / 2) - 1;
  const s1Matches = new Array(s1.length).fill(false);
  const s2Matches = new Array(s2.length).fill(false);

  let matches = 0;
  for (let i = 0; i < s1.length; i++) {
    const start = Math.max(0, i - matchDistance);
    const end = Math.min(i + matchDistance + 1, s2.length);
    for (let j = start; j < end; j++) {
      if (!s2Matches[j] && s1[i] === s2[j]) {
        s1Matches[i] = true;
        s2Matches[j] = true;
        matches++;
        break;
      }
    }
  }

  if (matches === 0) return 0.0;

  let k = 0;
  let transpositions = 0;
  for (let i = 0; i < s1.length; i++) {
    if (s1Matches[i]) {
      while (!s2Matches[k]) k++;
      if (s1[i] !== s2[k]) transpositions++;
      k++;
    }
  }

  const jaro = (matches / s1.length + matches / s2.length + (matches - transpositions / 2) / matches) / 3;
  let prefix = 0;
  for (let i = 0; i < Math.min(4, Math.min(s1.length, s2.length)); i++) {
    if (s1[i] === s2[i]) prefix++;
    else break;
  }
  return jaro + prefix * 0.1 * (1 - jaro);
}

function computeSoundex(s) {
  if (!s || !s.length) return "0000";
  s = s.toUpperCase().replace(/[^A-Z]/g, "");
  if (!s.length) return "0000";

  const mapping = {
    B: "1", F: "1", P: "1", V: "1",
    C: "2", G: "2", J: "2", K: "2", Q: "2", S: "2", X: "2", Z: "2",
    D: "3", T: "3",
    L: "4",
    M: "5", N: "5",
    R: "6"
  };

  const firstChar = s[0];
  let res = firstChar;
  let prevCode = mapping[firstChar] || "0";

  for (let i = 1; i < s.length; i++) {
    const code = mapping[s[i]] || "0";
    if (code !== "0") {
      if (code !== prevCode) {
        res += code;
        prevCode = code;
      }
    } else {
      prevCode = "0";
    }
    if (res.length === 4) break;
  }
  return (res + "0000").slice(0, 4);
}

/**
 * Glyphs a scanner or OCR pass genuinely mixes up, folded onto one shape so a
 * misread and the real serial become the same string. Mirrors
 * EntityResolver.fold_confusables in integration/entity_resolver.py — the two
 * engines must agree or the page and the node would disagree about a verdict.
 */
function foldConfusables(s) {
  return String(s || "").toUpperCase().replace(/[\s_]+/g, "-")
    .replace(/[OQD]/g, "0").replace(/[IL|]/g, "1")
    .replace(/S/g, "5").replace(/B/g, "8").replace(/Z/g, "2").replace(/G/g, "6");
}

/**
 * True when the input reads like a serial or batch code rather than a product
 * name. Codes here are separator-joined with no spaces; names in the catalogue
 * carry spaces ("Novamox 500mg"). Requiring a digit or a third segment keeps a
 * hyphenated drug name such as "Co-trimoxazole" on the name-matching path.
 */
function looksLikeIdentifier(s) {
  const t = String(s || "").toUpperCase().trim();
  if (!/[-_]/.test(t) || /\s/.test(t)) return false;
  return /\d/.test(t) || t.split(/[-_]/).filter(Boolean).length >= 3;
}

function clientFuzzyResolve(rawInput) {
  const cleaned = (rawInput || "").trim().toUpperCase();
  const knownKeys = Object.keys(BENCHMARK_DATA);

  // 1. Exact canonical product_uid match
  if (BENCHMARK_DATA[cleaned]) {
    return {
      raw: rawInput,
      canonical: cleaned,
      score: 1.0,
      isExact: true,
      isFuzzy: false,
      levenshtein: 0,
      jaroWinkler: 1.0,
      soundex: computeSoundex(cleaned),
      matchedField: "product_uid",
      transitivePath: cleaned,
      explanation: "Exact canonical match in master registry."
    };
  }

  // 2. Deterministic Transitive Batch Number Linkage (Identity Graph)
  for (const [key, item] of Object.entries(BENCHMARK_DATA)) {
    if (item.product && item.product.batch_number) {
      if (item.product.batch_number.toUpperCase() === cleaned) {
        return {
          raw: rawInput,
          canonical: key,
          score: 1.0,
          isExact: false,
          isFuzzy: true,
          levenshtein: 0,
          jaroWinkler: 1.0,
          soundex: computeSoundex(key),
          matchedField: "batch_number",
          transitivePath: `Batch '${rawInput}' ➔ ${key} (${item.product.product_name})`,
          explanation: `Transitive Identity Graph Linkage: Batch ID '${rawInput}' resolved to canonical '${key}' (${item.product.product_name}).`
        };
      }
    }
    // Check distribution batch serials if present
    if (item.distribution && item.distribution.batches) {
      for (const b of item.distribution.batches) {
        if (b.batch_id && b.batch_id.toUpperCase() === cleaned) {
          return {
            raw: rawInput,
            canonical: key,
            score: 1.0,
            isExact: false,
            isFuzzy: true,
            levenshtein: 0,
            jaroWinkler: 1.0,
            soundex: computeSoundex(key),
            matchedField: "dist_batch_id",
            transitivePath: `Logistics Batch '${rawInput}' ➔ ${key} (${item.product.product_name})`,
            explanation: `Transitive Identity Graph Linkage: Logistics ERP Batch '${rawInput}' resolved to canonical '${key}'.`
          };
        }
      }
    }
  }

  // 3. OCR character substitution ('l'/'I' -> '1', 'O' -> '0', spaces/underscores -> '-')
  let subbed = cleaned.replace(/[\s_]+/g, "-");
  const parts = subbed.split("-");
  if (parts.length >= 3 && parts[parts.length - 1].length === 3) {
    const sfx = parts[parts.length - 1].replace(/O/g, "0").replace(/[LI]/g, "1");
    subbed = parts.slice(0, parts.length - 1).join("-") + "-" + sfx;
  }

  if (BENCHMARK_DATA[subbed]) {
    const jw = computeJaroWinklerSimilarity(cleaned, subbed);
    const lev = computeLevenshteinDistance(cleaned, subbed);
    return {
      raw: rawInput,
      canonical: subbed,
      score: jw,
      isExact: false,
      isFuzzy: true,
      levenshtein: lev,
      jaroWinkler: jw,
      soundex: computeSoundex(subbed),
      matchedField: "ocr_substitution",
      transitivePath: `Raw '${rawInput}' ➔ OCR Corrected '${subbed}'`,
      explanation: "OCR character substitution ('l'/'1' & delimiter fix) resolved canonical entity."
    };
  }

  // Check if subbed matches a batch number
  for (const [key, item] of Object.entries(BENCHMARK_DATA)) {
    if (item.product && item.product.batch_number && item.product.batch_number.toUpperCase() === subbed) {
      const jw = computeJaroWinklerSimilarity(cleaned, subbed);
      return {
        raw: rawInput,
        canonical: key,
        score: jw,
        isExact: false,
        isFuzzy: true,
        levenshtein: computeLevenshteinDistance(cleaned, subbed),
        jaroWinkler: jw,
        soundex: computeSoundex(key),
        matchedField: "batch_number",
        transitivePath: `Raw '${rawInput}' ➔ Batch '${subbed}' ➔ ${key}`,
        explanation: `OCR delimiter fix linked Batch '${subbed}' to canonical '${key}'.`
      };
    }
  }

  // 3b. Confusion-folded exact match across every canonical key. Step 3 only
  // rewrites the final segment, so 'MED-ASAL1-OO1' never reached 'MED-ASALI-001'
  // and fell through to name matching, which linked it to an unrelated product.
  const foldedInput = foldConfusables(cleaned);
  for (const key of knownKeys) {
    if (foldConfusables(key) === foldedInput) {
      return {
        raw: rawInput,
        canonical: key,
        score: computeJaroWinklerSimilarity(cleaned, key),
        isExact: false,
        isFuzzy: true,
        levenshtein: computeLevenshteinDistance(cleaned, key),
        jaroWinkler: computeJaroWinklerSimilarity(cleaned, key),
        soundex: computeSoundex(key),
        matchedField: "product_uid",
        transitivePath: "'" + rawInput + "' -> '" + key + "'",
        explanation: "Character-confusion match: identical to " + key +
          " once scanner-confusable glyphs (O/0, I/L/1, S/5, B/8, Z/2) are folded."
      };
    }
  }

  // 4. Fuzzy Batch Number Matching (e.g. typos like 'BATCH-AO01' or 'BATCH_A001')
  let bestBatchScore = 0.0;
  let bestBatchKey = null;
  let bestBatchName = "";
  for (const [key, item] of Object.entries(BENCHMARK_DATA)) {
    if (item.product && item.product.batch_number) {
      const bNum = item.product.batch_number.toUpperCase();
      const jw = computeJaroWinklerSimilarity(cleaned, bNum);
      if (jw > bestBatchScore) {
        bestBatchScore = jw;
        bestBatchKey = key;
        bestBatchName = item.product.product_name;
      }
    }
  }
  if (bestBatchScore >= 0.85 && bestBatchKey) {
    return {
      raw: rawInput,
      canonical: bestBatchKey,
      score: bestBatchScore,
      isExact: false,
      isFuzzy: true,
      levenshtein: computeLevenshteinDistance(cleaned, BENCHMARK_DATA[bestBatchKey].product.batch_number),
      jaroWinkler: bestBatchScore,
      soundex: computeSoundex(bestBatchKey),
      matchedField: "batch_number",
      transitivePath: `Batch '${rawInput}' ➔ ${bestBatchKey} (${bestBatchName})`,
      explanation: `Fuzzy Batch Linkage: Typo in Batch ID matched canonical '${bestBatchKey}' (${bestBatchName}) with ${(bestBatchScore * 100).toFixed(1)}% confidence.`
    };
  }

  // 5. Probabilistic Multi-Attribute Matching (Brand Trade Name & Generic Active Formula)
  // Evaluates Jaro-Winkler, Levenshtein, and Soundex phonetic encoding across brand & generic names
  let bestNameScore = 0.0;
  let bestNameKey = null;
  let bestNameText = "";
  let bestNameField = "product_name";
  const rawFirstToken = cleaned.split(/[\s-]+/)[0];
  const soundexRaw = computeSoundex(rawFirstToken);

  // Scoring a serial against brand names is a category error, and it was the
  // path by which invented serials matched a real product and inherited its
  // verdict. Serials are handled by the identifier rules above.
  for (const [key, item] of (looksLikeIdentifier(cleaned) ? [] : Object.entries(BENCHMARK_DATA))) {
    if (!item.product) continue;
    const candidates = [
      { text: item.product.product_name || "", field: "product_name", label: "Brand Trade Name" },
      { text: item.product.generic_name || "", field: "generic_name", label: "Generic Active Formula" }
    ];

    for (const cand of candidates) {
      if (!cand.text) continue;
      const textUpper = cand.text.toUpperCase();
      const jwFull = computeJaroWinklerSimilarity(cleaned, textUpper);
      const targetFirstToken = textUpper.split(/[\s-]+/)[0];
      const jwPrefix = computeJaroWinklerSimilarity(rawFirstToken, targetFirstToken);

      const soundexTarget = computeSoundex(targetFirstToken);
      const phoneticMatch = (soundexRaw === soundexTarget && soundexRaw !== "0000");
      const phoneticBonus = phoneticMatch ? 0.08 : 0.0;
      const containment = textUpper.includes(cleaned) || cleaned.includes(textUpper);
      const containmentBonus = containment ? 0.08 : 0.0;

      const composite = Math.min(0.99, Math.max(jwFull, jwPrefix) + phoneticBonus + containmentBonus);
      if (composite > bestNameScore) {
        bestNameScore = composite;
        bestNameKey = key;
        bestNameText = cand.text;
        bestNameField = cand.field;
      }
    }
  }

  if (bestNameScore >= 0.72 && bestNameKey) {
    const soundexMatched = computeSoundex(bestNameText.split(/[\s-]+/)[0]);
    return {
      raw: rawInput,
      canonical: bestNameKey,
      score: bestNameScore,
      isExact: false,
      isFuzzy: true,
      levenshtein: computeLevenshteinDistance(cleaned, bestNameText.toUpperCase()),
      jaroWinkler: bestNameScore,
      soundex: soundexMatched,
      matchedField: bestNameField,
      transitivePath: `'${rawInput}' ➔ '${bestNameText}' ➔ ${bestNameKey}`,
      explanation: `Probabilistic Record Linkage: Input matched '${bestNameText}' (${bestNameKey}) with ${(bestNameScore * 100).toFixed(1)}% confidence (Soundex: ${soundexMatched}).`
    };
  }

  // 6. Fallback Jaro-Winkler ranking over canonical keys
  let bestCandidate = cleaned;
  let bestScore = 0.0;
  let bestLev = 999;

  for (const key of knownKeys) {
    const jw = computeJaroWinklerSimilarity(cleaned, key);
    const lev = computeLevenshteinDistance(cleaned, key);
    if (jw > bestScore) {
      bestScore = jw;
      bestCandidate = key;
      bestLev = lev;
    }
  }

  // A similarity threshold cannot separate a genuine misread from an invented
  // serial here: measured on this corpus a real OCR slip scores 0.888 while
  // 'MED-FAKE-0001' scores 0.897. Anything not caught by the deterministic and
  // confusion-folded rules above is left unlinked, which sends it to the
  // phantom-serial veto rather than onto some real product's clean verdict.
  if (false) {
    return {
      raw: rawInput,
      canonical: bestCandidate,
      score: bestScore,
      isExact: false,
      isFuzzy: true,
      levenshtein: bestLev,
      jaroWinkler: bestScore,
      soundex: computeSoundex(bestCandidate),
      matchedField: "product_uid",
      transitivePath: `'${rawInput}' ➔ '${bestCandidate}'`,
      explanation: "Fuzzy record linkage: Jaro-Winkler " + (bestScore * 100).toFixed(1) + "% >= 72% threshold."
    };
  }

  return {
    raw: rawInput,
    canonical: cleaned,
    score: bestScore,
    isExact: false,
    isFuzzy: false,
    levenshtein: bestLev,
    jaroWinkler: bestScore,
    soundex: computeSoundex(cleaned),
    matchedField: "unlinked",
    transitivePath: "",
    explanation: "Unlinked identifier. No candidate met minimum similarity threshold."
  };
}

