-- Neovim >= 0.11. Load explicitly from your trusted init.lua.
-- Install lifetxt in this interpreter first; no automatic installation/scanning.
vim.filetype.add({
  extension = { lifetxt = 'lifetxt' },
  filename = { ['life.txt'] = 'lifetxt', ['.life.txt'] = 'lifetxt' },
  pattern = { ['.*%.life%.txt'] = 'lifetxt', ['.*_life%.txt'] = 'lifetxt' },
})
vim.lsp.config('lifetxt', {
  cmd = { 'python', '-m', 'lifetxt.lsp', '--stdio' },
  filetypes = { 'lifetxt' },
  root_markers = { '.git' },
  settings = {},
  flags = { debounce_text_changes = 200 },
})
vim.lsp.enable('lifetxt')
-- Weekly files: :setfiletype lifetxt (no global *.txt association).
-- Disable: vim.lsp.enable('lifetxt', false).
