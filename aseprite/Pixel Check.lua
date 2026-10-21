-- Pixel Check: analisa o frame atual com o pixelclean.py e mostra as marcas numa camada "check" por cima.
-- A janela explica cada problema, como corrigir, e pode aplicar a cor sugerida (Ctrl+Z desfaz).
-- Exemplos de treino: o 1º Pixel Check de um frame guarda o "antes" (temporário). Nada vai pra pasta
-- dados/ até você clicar "Salvar exemplo"; "Descartar" joga o antes fora.
-- Instalar: copiar este arquivo pra pasta de scripts do Aseprite (File > Scripts > Open Scripts Folder),
-- depois File > Scripts > Rescan. Atalho: Edit > Keyboard Shortcuts, procurar "Pixel Check".

local PYTHON = "python"
local SCRIPT = [[C:\Users\guilm\OneDrive\Documentos\Pixel_Art_Projeto\pixelclean.py]]
local DATA_DIR = [[C:\Users\guilm\OneDrive\Documentos\Pixel_Art_Projeto\dados]]
local LAYER_NAME = "check"
local COLORS = {  -- mesmas cores do LINT no pixelclean.py, só pra legenda
  ["degraus"] = "amarelo", ["contorno 2px"] = "azul", ["banding"] = "roxo", ["se misturam"] = "ciano",
  ["cotovelos"] = "laranja", ["tom solto"] = "vermelho", ["pescoço"] = "verde", ["pillow shading"] = "rosa",
}

local spr = app.activeSprite
if not spr then return app.alert("Abra um sprite primeiro.") end
if spr.colorMode ~= ColorMode.RGB then
  return app.alert("Pixel Check precisa de sprite RGB (Sprite > Color Mode > RGB Color).")
end

local frame = app.activeFrame
local check, target
for _, l in ipairs(spr.layers) do
  if l.name == LAYER_NAME then check = l end
end
-- camada onde as sugestões são aplicadas: a ativa, ou a de cima que não seja a "check"
target = app.activeLayer
if not target or target == check or not target.isImage then
  for i = #spr.layers, 1, -1 do
    local l = spr.layers[i]
    if l ~= check and l.isImage then target = l break end
  end
end

-- renderiza o frame sem a camada de marcas
if check then check.isVisible = false end
local img = Image(spr.width, spr.height, ColorMode.RGB)
img:drawSprite(spr, frame)

local tmp = app.fs.joinPath(app.fs.tempPath, "pixelcheck_in.png")
local out = app.fs.joinPath(app.fs.tempPath, "pixelcheck_marks.png")
os.remove(out)
os.remove(out .. ".view.png")  -- não mostrar prévia velha se o Python falhar
img:saveAs(tmp)

-- aspas extras por fora: o cmd do Windows engole o primeiro par
os.execute(string.format('""%s" "%s" "%s" "%s" --lint"', PYTHON, SCRIPT, tmp, out))

if not app.fs.isFile(out) then
  if check then check.isVisible = true end
  return app.alert("O Python nao gerou resultado. Teste no terminal: python \"" .. SCRIPT .. "\" --test")
end

local function copy(src, dst)
  local i = io.open(src, "rb")
  if not i then return end
  local o = io.open(dst, "wb")
  o:write(i:read("a"))
  o:close()
  i:close()
end

-- exemplo pendente deste sprite+frame: o "antes" fica guardado até salvar ou descartar
local PENDING_DIR = app.fs.joinPath(app.fs.tempPath, "pixelcheck_pendente")
app.fs.makeAllDirectories(PENDING_DIR)
local title = app.fs.fileTitle(spr.filename)
local key = (title ~= "" and title or "sem_nome"):gsub("[^%w_%-]", "_") .. "_f" .. frame.frameNumber
local function pend(name) return app.fs.joinPath(PENDING_DIR, key .. "_" .. name) end
local PENDING_FILES = { "antes.png", "relatorio.txt", "sugestoes.txt", "log.txt" }

local continuing = app.fs.isFile(pend("antes.png"))
if not continuing then
  copy(tmp, pend("antes.png"))
  copy(out .. ".txt", pend("relatorio.txt"))
  copy(out .. ".fix", pend("sugestoes.txt"))
  local log = io.open(pend("log.txt"), "w")
  log:write("inicio: " .. os.date("%Y-%m-%d %H:%M:%S") .. "\n")
  log:close()
end
local function log(text)
  local f = io.open(pend("log.txt"), "a")
  if f then f:write(text .. "\n") f:close() end
end

local marks = Image{ fromFile = out }
app.transaction("Pixel Check", function()
  if not check then
    check = spr:newLayer()
    check.name = LAYER_NAME
    check.opacity = 170
  end
  check.stackIndex = #spr.layers
  check.isVisible = true
  local cel = check:cel(frame)
  if cel then spr:deleteCel(cel) end
  spr:newCel(check, frame, marks, Point(0, 0))
end)
app.activeLayer = target
app.refresh()

-- a fonte pixelada do Aseprite não tem alguns acentos (á, ã...): troca pela letra sem acento
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

-- sugestões: "nome x y r g b a" (o nome pode ter espaço, então os 6 números vêm do fim)
local fixes = {}
for _, line in ipairs(lines(out .. ".fix")) do
  local name, x, y, r, g, b, a = line:match("^(.-) (%d+) (%d+) (%d+) (%d+) (%d+) (%d+)$")
  if name then
    fixes[name] = fixes[name] or {}
    table.insert(fixes[name], { tonumber(x), tonumber(y),
      app.pixelColor.rgba(tonumber(r), tonumber(g), tonumber(b), tonumber(a)) })
  end
end

local dlg = Dialog("Pixel Check - frame " .. frame.frameNumber)

-- prévia: tamanho real | ampliado | silhueta | desfocado
if app.fs.isFile(out .. ".view.png") then
  local view = Image{ fromFile = out .. ".view.png" }
  dlg:separator{ text = "Previa: tamanho real | ampliado | silhueta | desfocado" }
  dlg:canvas{ width = view.width, height = view.height,
              onpaint = function(ev) ev.context:drawImage(view, 0, 0) end }
  dlg:newrow()
  dlg:label{ text = "Se a silhueta nao se entende, ou o desfocado mostra manchas/linhas tortas, revise." }
end

local report = lines(out .. ".txt")
if #report == 0 then dlg:label{ text = "Nada encontrado neste frame." } end
for i, line in ipairs(report) do
  local name, why, how, count = line:match("^(.-)|(.-)|(.-)|(.-)$")
  if name == "dica" then
    dlg:separator{ text = "dica de cor (estilo, nao erro)" }
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

local before_apply  -- a camada como estava antes de aplicar, pro botão "Desfazer aplicação"

local function apply()
  local data = dlg.data
  local applied = {}
  local cur = target:cel(frame)
  before_apply = cur and { image = cur.image:clone(), position = cur.position } or { image = nil }
  app.transaction("Pixel Check: sugestões", function()
    local cel = target:cel(frame)
    local full = Image(spr.width, spr.height, ColorMode.RGB)
    if cel then full:drawImage(cel.image, cel.position) end
    for i, line in ipairs(report) do
      local name = line:match("^(.-)|")
      if data["fix" .. i] and fixes[name] then
        for _, p in ipairs(fixes[name]) do full:drawPixel(p[1], p[2], p[3]) end
        applied[#applied + 1] = name
      end
    end
    if cel then
      cel.image = full
      cel.position = Point(0, 0)
    else
      spr:newCel(target, frame, full, Point(0, 0))
    end
    local old = check:cel(frame)
    if old then spr:deleteCel(old) end  -- marcas antigas não valem mais
  end)
  app.refresh()
  log("aplicou: " .. (#applied > 0 and table.concat(applied, ", ") or "nada"))
  dlg:modify{ id = "undo", enabled = true }
  dlg:modify{ id = "status", text = "Aplicado. Nao gostou? 'Desfazer aplicacao'. Gostou? Rode o Pixel Check de novo." }
end

-- volta a camada pro jeito de antes do último "Aplicar marcados" (também vira 1 passo de Ctrl+Z)
local function undo_apply()
  if not before_apply then return end
  app.transaction("Pixel Check: desfazer sugestões", function()
    local cel = target:cel(frame)
    if before_apply.image then
      if cel then
        cel.image = before_apply.image
        cel.position = before_apply.position
      else
        spr:newCel(target, frame, before_apply.image, before_apply.position)
      end
    elseif cel then
      spr:deleteCel(cel)
    end
  end)
  before_apply = nil
  app.refresh()
  log("desfez a aplicacao")
  dlg:modify{ id = "undo", enabled = false }
  dlg:modify{ id = "status", text = "Desfeito: o desenho voltou a como estava antes de aplicar." }
end

-- o frame como está agora, sem a camada de marcas
local function render()
  local was = check.isVisible
  check.isVisible = false
  local im = Image(spr.width, spr.height, ColorMode.RGB)
  im:drawSprite(spr, frame)
  check.isVisible = was
  return im
end

local function discard()
  for _, name in ipairs(PENDING_FILES) do os.remove(pend(name)) end
end

local function save()
  if not app.fs.isFile(pend("antes.png")) then
    return dlg:modify{ id = "status", text = "Nao ha 'antes' guardado. Rode o Pixel Check de novo." }
  end
  local antes = Image{ fromFile = pend("antes.png") }
  local depois = render()
  if antes:isEqual(depois) and app.alert{ title = "Pixel Check", text = "Nada mudou desde o 'antes'. Salvar mesmo assim?",
                                          buttons = { "Salvar", "Cancelar" } } ~= 1 then
    return
  end
  local folder = os.date("%Y-%m-%d_%H%M%S") .. "_" .. key
  local dir = app.fs.joinPath(DATA_DIR, folder)
  app.fs.makeAllDirectories(dir)
  copy(pend("antes.png"), app.fs.joinPath(dir, "antes.png"))
  depois:saveAs(app.fs.joinPath(dir, "depois.png"))
  copy(pend("relatorio.txt"), app.fs.joinPath(dir, "relatorio.txt"))
  copy(pend("sugestoes.txt"), app.fs.joinPath(dir, "sugestoes.txt"))
  log("salvo: " .. os.date("%Y-%m-%d %H:%M:%S"))
  copy(pend("log.txt"), app.fs.joinPath(dir, "decisoes.txt"))
  -- comparação ampliada pra você conferir o exemplo: antes | depois
  local s = 4
  local a2, d2 = antes:clone(), depois:clone()
  a2:resize(antes.width * s, antes.height * s)
  d2:resize(depois.width * s, depois.height * s)
  local cmp = Image(a2.width * 2 + 8, a2.height, ColorMode.RGB)
  cmp:drawImage(a2, Point(0, 0))
  cmp:drawImage(d2, Point(a2.width + 8, 0))
  cmp:saveAs(app.fs.joinPath(dir, "comparacao.png"))
  discard()
  dlg:modify{ id = "save", enabled = false }
  dlg:modify{ id = "discard", enabled = false }
  dlg:modify{ id = "status", text = "Exemplo salvo em dados/" .. folder }
end

dlg:separator()
dlg:label{ text = "As sugestoes vao pra camada \"" .. target.name .. "\". É só um ponto de partida:" }
dlg:newrow()
dlg:label{ text = "assimetria, luz e estilo podem ser propositais." }
dlg:separator{ text = "Exemplo de treino (so salva se voce clicar)" }
dlg:label{ id = "status", text = continuing
  and "Continuando: o 'antes' e do 1o Pixel Check deste frame. Salve quando terminar."
  or "Novo exemplo: o 'antes' e o frame agora. Corrija e clique Salvar quando estiver bom." }
dlg:newrow()
dlg:button{ id = "apply", text = "Aplicar marcados", onclick = apply }
dlg:button{ id = "undo", text = "Desfazer aplicacao", enabled = false, onclick = undo_apply }
dlg:newrow()
dlg:button{ id = "save", text = "Salvar exemplo", onclick = save }
dlg:button{ id = "discard", text = "Descartar exemplo", onclick = function()
  discard()
  dlg:modify{ id = "save", enabled = false }
  dlg:modify{ id = "discard", enabled = false }
  dlg:modify{ id = "status", text = "Exemplo descartado (o desenho nao muda). O proximo Pixel Check comeca um 'antes' novo." }
end }
dlg:button{ text = "Fechar" }
dlg:show{ wait = false }
