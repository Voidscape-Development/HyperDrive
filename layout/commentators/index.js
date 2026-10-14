// The commentators, each with their name and, by the page's size option,
// pronouns, real name (normal) and Twitter (normal and mini)
const FIELDS = {
  normal: ["name", "pronoun", "real_name", "twitter"],
  mini: ["name", "pronoun", "twitter"],
  micro: ["name", "pronoun"],
};

HD.layout({
  settings: { size: "normal" },

  update(s) {
    HD.commentators(s, ".container", FIELDS[s.settings.size] || FIELDS.normal);
  },
});
