const layoutUrl = {
  read(params) {
    const values = params.getAll("layout");
    if (values.length !== 1 || values[0].length > 2048) return null;
    try {
      const value = JSON.parse(values[0]);
      return value?.v === 1 ? value : null;
    } catch (_) {
      return null;
    }
  },
  write(layout) {
    const url = new URL(location.href);
    url.searchParams.set("layout", JSON.stringify({v: 1, ...layout}));
    history.replaceState(history.state, "", url);
  },
};
