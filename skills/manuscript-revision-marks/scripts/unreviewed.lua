-- typeset.py --draft: turn the segments rev_marks.py marked unreviewed into LaTeX.
-- A div `::: unreviewed` (whole paragraphs) becomes the shaded `unreviewed` box; a span
-- `[...]{.unreviewed}` inside a paragraph is highlighted with soul's \hl when it is plain text, and
-- coloured otherwise (\hl cannot take citations, math, links, code or notes).
local PLAIN = { Str = true, Space = true, SoftBreak = true }

local function plain(inlines)
  for _, el in ipairs(inlines) do
    if not PLAIN[el.t] then
      return false
    end
  end
  return true
end

function Div(el)
  if el.classes:includes("unreviewed") then
    local out = { pandoc.RawBlock("latex", "\\begin{unreviewed}") }
    for _, block in ipairs(el.content) do
      table.insert(out, block)
    end
    table.insert(out, pandoc.RawBlock("latex", "\\end{unreviewed}"))
    return out
  end
end

function Span(el)
  if el.classes:includes("unreviewed") then
    local open = plain(el.content) and "\\hl{" or "{\\unrevtext{}"
    local out = { pandoc.RawInline("latex", open) }
    for _, inline in ipairs(el.content) do
      table.insert(out, inline)
    end
    table.insert(out, pandoc.RawInline("latex", "}"))
    return out
  end
end
