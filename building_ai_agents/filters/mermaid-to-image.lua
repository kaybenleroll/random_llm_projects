-- Convert ```mermaid code fences into rendered PNG images when mmdc is available.

local output_dir = os.getenv("MERMAID_OUTPUT_DIR") or ".build/mermaid"
local theme = os.getenv("MERMAID_THEME") or "default"
local scale = os.getenv("MERMAID_SCALE") or "2"
local puppeteer_config = os.getenv("MERMAID_PUPPETEER_CONFIG") or "filters/puppeteer-config.json"

local function shell_quote(value)
  return "'" .. tostring(value):gsub("'", "'\\''") .. "'"
end

local function ensure_dir(path)
  os.execute("mkdir -p " .. shell_quote(path))
end

local function file_exists(path)
  local f = io.open(path, "rb")
  if f then
    f:close()
    return true
  end
  return false
end

local function command_exists(name)
  local ok = os.execute("command -v " .. shell_quote(name) .. " >/dev/null 2>&1")
  return ok == true or ok == 0
end

function CodeBlock(el)
  if not el.classes:includes("mermaid") then
    return nil
  end

  if not command_exists("mmdc") then
    io.stderr:write("[mermaid-filter] mmdc not found; keeping mermaid block as code.\n")
    return el
  end

  ensure_dir(output_dir)

  local hash = pandoc.utils.sha1(el.text)
  local source_file = output_dir .. "/" .. hash .. ".mmd"
  local image_file = output_dir .. "/" .. hash .. ".png"

  if not file_exists(image_file) then
    local src = io.open(source_file, "w")
    if not src then
      io.stderr:write("[mermaid-filter] Failed writing temporary mermaid source.\n")
      return el
    end
    src:write(el.text)
    src:close()

    local cmd = table.concat({
      "mmdc",
      "-q",
      "-i", shell_quote(source_file),
      "-o", shell_quote(image_file),
      "-t", shell_quote(theme),
      "-s", shell_quote(scale),
      "-b", shell_quote("transparent"),
      file_exists(puppeteer_config) and ("-p " .. shell_quote(puppeteer_config)) or "",
      ">/dev/null 2>&1"
    }, " ")

    local ok = os.execute(cmd)
    if not (ok == true or ok == 0) then
      io.stderr:write("[mermaid-filter] Failed rendering mermaid diagram with mmdc (check Chromium and puppeteer config).\n")
      return el
    end
  end

  local caption = el.attributes["caption"] or "Mermaid diagram"
  return pandoc.Para({pandoc.Image(caption, image_file)})
end
