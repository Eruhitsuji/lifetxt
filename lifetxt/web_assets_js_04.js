    function i18nDictionary() {
      return UI_STRINGS[currentLanguage()] || null;
    }

    // Labels here are rarely bare words: they carry a leading icon, a live
    // count such as "Open (108)", or a shortcut hint such as "Refresh (r)".
    // Exact matching alone would leave most of the chrome untranslated, so
    // the affixes are peeled off, the core is translated, and they go back on.
    const I18N_PREFIX = /^([^\p{L}\p{N}]+)(.*)$/u;
    // The ASCII parens are written as escapes because they sit inside
    // character classes, where they cannot balance, and the page-wide
    // bracket-balance smoke test counts every bracket in the script.
    const I18N_SUFFIX = /^(.*?)(\s*[\u0028\uFF08][^\u0029\uFF09]*[\u0029\uFF09])$/u;

    /** Translate a string built in JavaScript. Falls back to the source. */
    function t(text) {
      const dict = i18nDictionary();
      if (!dict) return text;
      return translateString(String(text), dict);
    }

    function translateString(text, dict) {
      const trimmed = String(text).trim();
      if (!trimmed) return text;
      if (dict[trimmed]) return dict[trimmed];
      const whole = translateByPattern(trimmed);
      if (whole) return whole;

      let prefix = "";
      let core = trimmed;
      const prefixMatch = I18N_PREFIX.exec(core);
      if (prefixMatch && prefixMatch[2]) {
        prefix = prefixMatch[1];
        core = prefixMatch[2];
        // "📈 Completions (last 14 days)" is one dictionary key once the icon
        // is gone, so try it before the suffix rule splits off "(last 14 days)".
        if (dict[core.trim()]) return prefix + dict[core.trim()];
      }

      let suffix = "";
      const suffixMatch = I18N_SUFFIX.exec(core);
      if (suffixMatch && suffixMatch[1].trim()) {
        core = suffixMatch[1];
        suffix = suffixMatch[2];
      }

      const base = core.trim();
      const replacement = dict[base] || translateByPattern(base);
      if (!replacement) return text;
      return prefix + replacement + suffix;
    }

    /** Translate a label whose text embeds a date, count, or duration. */
    function translateByPattern(text) {
      const patterns = I18N_PATTERNS[currentLanguage()];
      if (!patterns) return "";
      for (const [regex, template] of patterns) {
        const match = regex.exec(text);
        if (match) {
          return template.replace(/\$(\d)/g, (_, index) => match[Number(index)] || "");
        }
      }
      return "";
    }

    function translateTree(root) {
      const dict = i18nDictionary();
      if (!dict || !root) return;

      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
        acceptNode(node) {
          // Never touch user content, scripts, styles, or editable fields.
          if (!node.nodeValue || !node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
          let el = node.parentElement;
          while (el) {
            if (el.hasAttribute && el.hasAttribute("data-no-i18n")) return NodeFilter.FILTER_REJECT;
            // Rendered record rows carry life.txt content, so a record titled
            // "Done" must not be rewritten as if it were a button label.
            if (el.classList && I18N_RECORD_CLASSES.some(c => el.classList.contains(c))) {
              return NodeFilter.FILTER_REJECT;
            }
            const tag = el.tagName;
            if (tag === "SCRIPT" || tag === "STYLE" || tag === "TEXTAREA") return NodeFilter.FILTER_REJECT;
            if (el.isContentEditable) return NodeFilter.FILTER_REJECT;
            el = el.parentElement;
          }
          return NodeFilter.FILTER_ACCEPT;
        },
      });

      const pending = [];
      let node = walker.nextNode();
      while (node) {
        pending.push(node);
        node = walker.nextNode();
      }
      for (const textNode of pending) {
        const raw = textNode.nodeValue;
        const trimmed = raw.trim();
        const replacement = translateString(trimmed, dict);