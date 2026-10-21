-- Junta as camadas geradas pelo base.py num .aseprite. Rodar em batch:
--   Aseprite.exe -b --script template/montar_aseprite.lua
local dir = app.fs.filePath(app.fs.normalizePath(debug.getinfo(1, "S").source:sub(2)))
local spr = Sprite(48, 48, ColorMode.RGB)
spr.layers[1].name = "contorno"
local function put(layer, name)
  spr:newCel(layer, 1, Image{ fromFile = app.fs.joinPath(dir, "camadas", name .. ".png") }, Point(0, 0))
end
put(spr.layers[1], "contorno")
-- mesma ordem do ORDEM no base.py (de baixo pra cima)
for _, name in ipairs{ "pe_esq", "pe_dir", "canela_esq", "canela_dir", "coxa_esq", "coxa_dir", "cintura", "peito",
                       "braco_esq", "braco_dir", "antebraco_esq", "antebraco_dir", "mao_esq", "mao_dir",
                       "cabeca", "guias" } do
  local l = spr:newLayer()
  l.name = name
  put(l, name)
end
spr.layers[#spr.layers].opacity = 160  -- guias meio transparentes; esconda quando quiser
spr:saveAs(app.fs.joinPath(dir, "base_frente.aseprite"))
print("salvo: " .. app.fs.joinPath(dir, "base_frente.aseprite"))
