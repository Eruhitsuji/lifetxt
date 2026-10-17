-- Actual built-in LSP client probe; output is sanitized fixture data only.
local fixture = vim.json.decode(table.concat(vim.fn.readfile('tests/fixtures/editor/interop.json'), '\n'))
local output = { client = 'Neovim ' .. tostring(vim.version()) }
local buf = vim.api.nvim_create_buf(true, false)
vim.api.nvim_set_current_buf(buf)
vim.api.nvim_buf_set_name(buf, 'lifetxt-probe.life.txt')
vim.api.nvim_buf_set_lines(buf, 0, -1, false, vim.split(fixture.text, '\n', { plain = true }))
vim.bo[buf].filetype = 'lifetxt'
local id = vim.lsp.start({ name = 'lifetxt', cmd = { os.getenv('LIFETXT_TEST_PYTHON'), '-m', 'lifetxt.lsp', '--stdio' }, root_dir = vim.fn.getcwd(), flags = { debounce_text_changes = 10 } })
assert(vim.wait(15000, function() return #vim.diagnostic.get(buf) > 0 end, 50), 'No diagnostics from Neovim')
output.diagnostics = vim.tbl_map(function(d)
 return { code = d.code, severity = d.severity, range = { start = { line = d.lnum, character = vim.str_utfindex(vim.api.nvim_buf_get_lines(buf, d.lnum, d.lnum + 1, false)[1], 'utf-16', d.col) }, ['end'] = { line = d.end_lnum, character = vim.str_utfindex(vim.api.nvim_buf_get_lines(buf, d.end_lnum, d.end_lnum + 1, false)[1], 'utf-16', d.end_col) } } }
end, vim.diagnostic.get(buf))
local client = vim.lsp.get_client_by_id(id)
local uri = vim.uri_from_bufnr(buf)
local h = client:request_sync('textDocument/hover', { textDocument = { uri = uri }, position = fixture.hover }, 5000, buf)
assert(h and h.result, 'No hover')
output.hover = h.result
vim.api.nvim_buf_set_lines(buf, 0, -1, false, { fixture.completionText })
vim.wait(100)
local result = client:request_sync('textDocument/completion', { textDocument = { uri = uri }, position = { line = 0, character = vim.str_utfindex(fixture.completionText, 'utf-16') } }, 5000, buf)
assert(result and result.result, 'No completion')
output.completion = vim.tbl_map(function(x) return x.label end, result.result)
assert(vim.deep_equal(output.completion, fixture.expectedCompletion))
vim.fn.writefile({vim.json.encode(output)}, os.getenv('LIFETXT_TEST_OUTPUT'))
client:stop()
vim.wait(500, function() return client:is_stopped() end, 10)
vim.cmd('qa!')
