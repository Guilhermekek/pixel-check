-- Pixel Check Animacao: compara os frames entre si (pixel tremendo, cor piscando, pé mudando de altura).
-- Usa os frames da tag onde está o frame atual; sem tag, usa todos os frames.
-- Marcas vão pra camada "check" (um cel por frame). A janela pode aplicar as sugestões (Ctrl+Z desfaz).

local PYTHON = "python"
local SCRIPT = [[C:\Users\guilm\OneDrive\Documentos\Pixel_Art_Projeto\pixelclean.py]]
local LAYER_NAME = "check"
local COLORS = { ["tremendo"] = "amarelo", ["cor piscando"] = "rosa" }

local spr = app.activeSprite
if not spr then return app.alert("Abra um sprite primeiro.") end
if spr.colorMode ~= ColorMode.RGB then
  return app.alert("Pixel Check precisa de sprite RGB (Sprite > Color Mode > RGB Color).")
end

-- quais frames: a tag do frame atual, ou todos
local first, last, what = 1, #spr.frames, "todos os frames"
for _, tag in ipairs(spr.tags) do
  if app.activeFrame.frameNumber >= tag.fromFrame.frameNumber and app.activeFrame.frameNumber <= tag.toFrame.frameNumber then
    first, last, what = tag.fromFrame.frameNumber, tag.toFrame.frameNumber, "tag \"" .. tag.name .. "\""
  end
end
local n = last - first + 1
if n < 3 then return app.alert("Precisa de pelo menos 3 frames pra comparar.") end

local check, target
for _, l in ipairs(spr.layers) do
  if l.name == LAYER_NAME then check = l end
end
target = app.activeLayer
if not target or target == check or not target.isImage then
  for i = #spr.layers, 1, -1 do
    local l = spr.layers[i]
    if l ~= check and l.isImage then target = l break end
  end
end

-- tira horizontal com os frames lado a lado, sem a camada de marcas
if check then check.isVisible = false end
local w, h = spr.width, spr.height
local strip = Image(w * n, h, ColorMode.RGB)
for i = 0, n - 1 do strip:drawSprite(spr, first + i, Point(i * w, 0)) end

local tmp = app.fs.joinPath(app.fs.tempPath, "pixelcheck_anim_in.png")
local out = app.fs.joinPath(app.fs.tempPath, "pixelcheck_anim_marks.png")
os.remove(out)
strip:saveAs(tmp)
os.execute(string.format('""%s" "%s" "%s" "%s" --anim %d"', PYTHON, SCRIPT, tmp, out, n))

if not app.fs.isFile(out) then
  if check then check.isVisible = true end
  return app.alert("O Python nao gerou resultado. Teste no terminal: python \"" .. SCRIPT .. "\" --test")
end

local marks = Image{ fromFile = out }
app.transaction("Pixel Check Animacao", function()
  if not check then
    check = spr:newLayer()
    check.name = LAYER_NAME
    check.opacity = 170
  end
  check.stackIndex = #spr.layers
  check.isVisible = true
  for i = 0, n - 1 do
    local f = first + i
    local old = check:cel(f)
    if old then spr:deleteCel(old) end
    local piece = Image(w, h, ColorMode.RGB)
    piece:drawImage(marks, Point(-i * w, 0))
    if not piece:isEmpty() then spr:newCel(check, f, piece, Point(0, 0)) end
  end
end)
app.activeLayer = target
app.refresh()

local PLAIN = { ["á"] = "a", ["à"] = "a", ["â"] = "a", ["ã"] = "a", ["õ"] = "o", ["ô"] = "o",
                ["ê"] = "e", ["í"] = "i", ["ú"] = "u" }
local function plain(s)
  for k, v in pairs(PLAIN) do s = s:gsub(k, v) end
  return s
end
local function lines(path)
  local t, f = {}, io.open(path, "r")
  if f then
    for line in f:lines() do if line ~= "" then t[#t + 1] = plain(line) end end
    f:close()
  end
  return t
end

-- sugestões: "nome frame x y r g b a" (frame relativo à tira, começando em 1)
local fixes = {}
for _, line in ipairs(lines(out .. ".fix")) do
  local name, fr, x, y, r, g, b, a = line:match("^(.-) (%d+) (%d+) (%d+) (%d+) (%d+) (%d+) (%d+)$")
  if name then
    fixes[name] = fixes[name] or {}
    table.insert(fixes[name], { first + tonumber(fr) - 1, tonumber(x), tonumber(y),
      app.pixelColor.rgba(tonumber(r), tonumber(g), tonumber(b), tonumber(a)) })
  end
end

local dlg = Dialog("Pixel Check Animacao - " .. what)
local report = lines(out .. ".txt")
if #report == 0 then dlg:label{ text = "Nada encontrado entre os frames." } end
for i, line in ipairs(report) do
  local name, why, how, count = line:match("^(.-)|(.-)|(.-)|(.-)$")
  if name == "dica" then
    dlg:separator{ text = "dica" }
  else
    dlg:separator{ text = name .. " (" .. (COLORS[name] or "?") .. ") - " .. count .. " px" }
  end
  dlg:label{ text = why }
  dlg:newrow()
  dlg:label{ text = "Como corrigir: " .. how }
  if fixes[name] then
    dlg:newrow()
    dlg:check{ id = "fix" .. i, text = "aplicar a cor sugerida", selected = false }
  end
end

local function apply()
  local data = dlg.data
  app.transaction("Pixel Check Animacao: sugestoes", function()
    local byFrame = {}
    for i, line in ipairs(report) do
      local name = line:match("^(.-)|")
      if data["fix" .. i] and fixes[name] then
        for _, p in ipairs(fixes[name]) do
          byFrame[p[1]] = byFrame[p[1]] or {}
          table.insert(byFrame[p[1]], p)
        end
      end
    end
    for f, list in pairs(byFrame) do
      local cel = target:cel(f)
      local full = Image(w, h, ColorMode.RGB)
      if cel then full:drawImage(cel.image, cel.position) end
      for _, p in ipairs(list) do full:drawPixel(p[2], p[3], p[4]) end
      if cel then
        cel.image = full
        cel.position = Point(0, 0)
      else
        spr:newCel(target, f, full, Point(0, 0))
      end
      local old = check:cel(f)
      if old then spr:deleteCel(old) end
    end
  end)
  app.refresh()
  dlg:close()
  app.alert("Sugestoes aplicadas na camada \"" .. target.name .. "\". Ctrl+Z desfaz.")
end

dlg:separator()
dlg:label{ text = "Use em animacoes no tempo (idle, andar, ataque). Numa rotacao de direcoes," }
dlg:newrow()
dlg:label{ text = "os frames sao diferentes de proposito e o 'tremendo' marca quase tudo." }
dlg:button{ text = "Aplicar marcados", onclick = apply }
dlg:button{ text = "Fechar" }
dlg:show{ wait = false }
