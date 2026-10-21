-- Espelhar Direcoes: gera o rascunho das direções que são espelho de outras (rotação de 8 direções).
-- Padrão (8 frames): 2->8, 3->7, 4->6. O personagem é espelhado em torno do próprio centro (fica no mesmo lugar).
-- Frame de destino vazio: copia camada por camada. Já tem desenho: o espelho vai pra camada "espelho (rascunho)"
-- e o seu desenho não é tocado. Assimetrias (rabo de cavalo, alça) ficam do lado errado: ajuste à mão.

local DRAFT = "espelho (rascunho)"

local spr = app.activeSprite
if not spr then return app.alert("Abra um sprite primeiro.") end

local function skip(l) return l.name == "check" or l.name == DRAFT or not l.isImage end

local function opaque(px)
  if spr.colorMode == ColorMode.RGB then return app.pixelColor.rgbaA(px) > 0 end
  if spr.colorMode == ColorMode.GRAY then return app.pixelColor.grayaA(px) > 0 end
  return px ~= spr.transparentColor
end

-- frame achatado (só camadas de desenho visíveis)
local function flat(f)
  local hidden = {}
  for _, l in ipairs(spr.layers) do
    if skip(l) and l.isVisible then l.isVisible = false; hidden[#hidden + 1] = l end
  end
  local img = Image(spr.spec)
  img:drawSprite(spr, f)
  for _, l in ipairs(hidden) do l.isVisible = true end
  return img
end

local function mirrored(src, pos, axis2)  -- axis2 = minX + maxX do personagem: x novo = axis2 - x
  local out = Image(spr.spec)
  for it in src:pixels() do
    local px = it()
    if opaque(px) then
      local x = axis2 - (it.x + pos.x)
      local y = it.y + pos.y
      if x >= 0 and x < spr.width then out:drawPixel(x, y, px) end
    end
  end
  return out
end

local function mirror(pairs)
  local report = {}
  app.transaction("Espelhar direcoes", function()
    for _, p in ipairs(pairs) do
      local s, t = p[1], p[2]
      local whole = flat(s)
      local minx, maxx
      for it in whole:pixels() do
        if opaque(it()) then
          minx = math.min(minx or it.x, it.x)
          maxx = math.max(maxx or it.x, it.x)
        end
      end
      if not minx then
        report[#report + 1] = "frame " .. s .. " esta vazio, pulei"
      else
        local axis2 = minx + maxx
        local empty = true
        for _, l in ipairs(spr.layers) do
          local c = not skip(l) and l:cel(t)
          if c and not c.image:isEmpty() then empty = false end
        end
        if empty then
          for _, l in ipairs(spr.layers) do
            local c = not skip(l) and l:cel(s)
            if c then
              local old = l:cel(t)
              if old then spr:deleteCel(old) end
              spr:newCel(l, t, mirrored(c.image, c.position, axis2), Point(0, 0))
            end
          end
          report[#report + 1] = "frame " .. s .. " -> " .. t .. ": copiado nas camadas"
        else
          local draft
          for _, l in ipairs(spr.layers) do if l.name == DRAFT then draft = l end end
          if not draft then
            draft = spr:newLayer()
            draft.name = DRAFT
          end
          local old = draft:cel(t)
          if old then spr:deleteCel(old) end
          spr:newCel(draft, t, mirrored(whole, Point(0, 0), axis2), Point(0, 0))
          report[#report + 1] = "frame " .. s .. " -> " .. t .. ": ja tinha desenho, foi pra camada '" .. DRAFT .. "'"
        end
      end
    end
  end)
  app.refresh()
  return report
end

local n = #spr.frames
local DEFAULT = { { 2, 8 }, { 3, 7 }, { 4, 6 } }

if not app.isUIAvailable then  -- modo batch (teste): usa o padrão direto
  for _, line in ipairs(mirror(n == 8 and DEFAULT or {})) do print(line) end
  return
end

local dlg = Dialog("Espelhar direcoes")
if n == 8 then
  dlg:combobox{ id = "dir", label = "Copiar", option = "2,3,4 -> 8,7,6",
                options = { "2,3,4 -> 8,7,6", "8,7,6 -> 2,3,4" } }
  for i, p in ipairs(DEFAULT) do
    dlg:check{ id = "p" .. i, text = "par " .. p[1] .. " / " .. p[2], selected = true }
  end
else
  dlg:label{ text = "O sprite tem " .. n .. " frames: escolha o par." }
  dlg:number{ id = "from", label = "Do frame", text = "1", decimals = 0 }
  dlg:number{ id = "to", label = "Para o frame", text = tostring(math.min(2, n)), decimals = 0 }
end
dlg:newrow()
dlg:label{ text = "Destino vazio: copia nas camadas. Com desenho: vai pra camada de rascunho." }
dlg:newrow()
dlg:label{ text = "Coisas assimetricas (rabo de cavalo, alca) ficam do lado errado: ajuste depois." }
dlg:button{ text = "Espelhar", onclick = function()
  local d, pairs = dlg.data, {}
  if n == 8 then
    for i, p in ipairs(DEFAULT) do
      if d["p" .. i] then
        pairs[#pairs + 1] = d.dir == "2,3,4 -> 8,7,6" and { p[1], p[2] } or { p[2], p[1] }
      end
    end
  else
    local a, b = math.floor(d.from), math.floor(d.to)
    if a < 1 or b < 1 or a > n or b > n or a == b then return app.alert("Frames invalidos.") end
    pairs = { { a, b } }
  end
  dlg:close()
  app.alert{ title = "Espelhar direcoes", text = mirror(pairs) }
end }
dlg:button{ text = "Cancelar" }
dlg:show{ wait = false }
