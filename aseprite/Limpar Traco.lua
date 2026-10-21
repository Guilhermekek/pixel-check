-- Limpar Traco: selecione um traço torto (laço ou retângulo) e rode. O pixelclean.py acha a linha que você
-- quis fazer e redesenha com degraus regulares (reta: degraus iguais; curva: degraus só crescendo/diminuindo).
-- O traço é a cor mais usada dentro da seleção, na camada ativa. Funciona melhor com a linha numa camada própria.

local PYTHON = "python"
local SCRIPT = [[C:\Users\guilm\OneDrive\Documentos\Pixel_Art_Projeto\pixelclean.py]]

local spr = app.activeSprite
if not spr then return app.alert("Abra um sprite primeiro.") end
if spr.colorMode ~= ColorMode.RGB then
  return app.alert("Limpar Traco precisa de sprite RGB (Sprite > Color Mode > RGB Color).")
end
local sel = spr.selection
if sel.isEmpty then
  return app.alert("Selecione o traco primeiro (laco ou retangulo em volta da linha).")
end
local layer, frame = app.activeLayer, app.activeFrame
if not layer or not layer.isImage or layer.name == "check" then
  return app.alert("Escolha a camada onde esta o traco.")
end
local cel = layer:cel(frame)
if not cel then return app.alert("Essa camada esta vazia neste frame.") end

-- camada inteira (tamanho do sprite) + máscara da seleção
local full = Image(spr.width, spr.height, ColorMode.RGB)
full:drawImage(cel.image, cel.position)
local mask = Image(spr.width, spr.height, ColorMode.RGB)
local white = app.pixelColor.rgba(255, 255, 255, 255)
local b = sel.bounds
for y = b.y, b.y + b.height - 1 do
  for x = b.x, b.x + b.width - 1 do
    if sel:contains(x, y) then mask:drawPixel(x, y, white) end
  end
end

local src = app.fs.joinPath(app.fs.tempPath, "pixeltrace_in.png")
local msk = app.fs.joinPath(app.fs.tempPath, "pixeltrace_sel.png")
local out = app.fs.joinPath(app.fs.tempPath, "pixeltrace_out.png")
os.remove(out)
full:saveAs(src)
mask:saveAs(msk)
os.execute(string.format('""%s" "%s" "%s" "%s" --trace "%s""', PYTHON, SCRIPT, src, out, msk))
if not app.fs.isFile(out) then
  return app.alert("Nada mudou: a selecao nao tem traco, ou o Python falhou (teste: python \"" .. SCRIPT .. "\" --test).")
end

local before = { image = cel.image:clone(), position = cel.position }
app.transaction("Limpar traco", function()
  cel.image = Image{ fromFile = out }
  cel.position = Point(0, 0)
end)
app.refresh()

local dlg = Dialog("Limpar traco")
dlg:label{ text = "Traco redesenhado com degraus regulares. Confira com zoom." }
dlg:newrow()
dlg:label{ text = "Dica: linha numa camada propria = o preenchimento nao e afetado." }
dlg:button{ text = "Manter" }
dlg:button{ text = "Desfazer", onclick = function()
  app.transaction("Limpar traco: desfazer", function()
    cel.image = before.image
    cel.position = before.position
  end)
  app.refresh()
  dlg:close()
end }
dlg:show{ wait = false }
