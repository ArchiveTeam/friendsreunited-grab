dofile("urlcode.lua")
dofile("table_show.lua")

local url_count = 0
local tries = 0
local item_type = os.getenv('item_type')
local item_value = os.getenv('item_value')
local item_dir = os.getenv('item_dir')
local warc_file_base = os.getenv('warc_file_base')
local item_type
local item_id_match
if item_type ~= "100discussions" then
  item_id = string.match(item_value, '([0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]%-[0-9a-f][0-9a-f][0-9a-f][0-9a-f]%-[0-9a-f][0-9a-f][0-9a-f][0-9a-f]%-[0-9a-f][0-9a-f][0-9a-f][0-9a-f]%-[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f])')
  item_id_match = string.gsub(item_id, '%-', '%%%-')
end

local downloaded = {}
local addedtolist = {}
local profiles = {}
local item_ids = {}
local recheck_urls = {}

for ignore in io.open("ignore-list", "r"):lines() do
  downloaded[ignore] = true
end

read_file = function(file)
  if file then
    local f = assert(io.open(file))
    local data = f:read("*all")
    f:close()
    return data
  else
    return ""
  end
end

add_item_ids = function(url)
  if string.match(url, item_id_match) then
    for itemid in string.gmatch(url, '([0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]%-[0-9a-f][0-9a-f][0-9a-f][0-9a-f]%-[0-9a-f][0-9a-f][0-9a-f][0-9a-f]%-[0-9a-f][0-9a-f][0-9a-f][0-9a-f]%-[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f])') do
      item_ids[itemid] = true
    end
  end
end

check_item_ids = function(url)
  for itemid in string.gmatch(url, '([0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]%-[0-9a-f][0-9a-f][0-9a-f][0-9a-f]%-[0-9a-f][0-9a-f][0-9a-f][0-9a-f]%-[0-9a-f][0-9a-f][0-9a-f][0-9a-f]%-[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f])') do
    if item_ids[itemid] == true then
      return true
    end
  end
  return false
end

wget.callbacks.download_child_p = function(urlpos, parent, depth, start_url_parsed, iri, verdict, reason)
  local url = urlpos["url"]["url"]
  local html = urlpos["link_expect_html"]

  url = string.gsub(url, "friendsreunited.(co[^:]+):80/", "friendsreunited.%1/")
 
  if (downloaded[url] ~= true and addedtolist[url] ~= true) and ((item_type == '100discussions' and string.match(url, item_value.."[0-9][0-9]") and not string.match(url, item_value.."[0-9][0-9][0-9]")) or html == 0 or string.match(url, "^https?://[^/]*friendsreunited%.co[^/]+/[pP]rofile") or check_item_ids(url) == true or string.match(url, "https?://[^/]*assetstorage%.co%.uk") or (item_type ~= "100discussions" and (string.match(url, item_id_match) or string.match(url, "^https?://[^/]*friendsreunited%.co[^/]+/[dD]iscussion/[vV]iew")))) then
    if string.match(url, "^https?://[^/]*friendsreunited%.co[^/]+/[pP]rofile/") then
      profiles[url] = true
      return false
    else
      add_item_ids(url)
      addedtolist[url] = true
      return true
    end
  else
    return false
  end
end


wget.callbacks.get_urls = function(file, url, is_css, iri)
  local urls = {}
  local html = nil

  downloaded[url] = true
  
  local function check(urla)
    local url = string.match(urla, "^([^#]+)")
    url = string.gsub(url, "friendsreunited.(co[^:]+):80/", "friendsreunited.%1/")
    if (downloaded[url] ~= true and addedtolist[url] ~= true) and ((item_type == '100discussions' and string.match(url, item_value.."[0-9][0-9]") and not string.match(url, item_value.."[0-9][0-9][0-9]")) or string.match(url, "^https?://[^/]*friendsreunited%.co[^/]+/[pP]rofile/") or check_item_ids == true or string.match(url, "https?://[^/]*assetstorage%.co%.uk") or (item_type ~= "100discussions" and (string.match(url, item_id_match) or string.match(url, "^https?://[^/]*friendsreunited%.co[^/]+/[dD]iscussion/[vV]iew")))) then
      if string.match(url, "^https?://[^/]*friendsreunited%.co[^/]+/[pP]rofile/") then
        profiles[url] = true
      elseif string.match(url, "&amp;") then
        add_item_ids(url)
        table.insert(urls, { url=string.gsub(url, "&amp;", "&") })
        addedtolist[url] = true
        addedtolist[string.gsub(url, "&amp;", "&")] = true
      else
        add_item_ids(url)
        table.insert(urls, { url=url })
        addedtolist[url] = true
      end
    elseif string.match(url, '[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]%-[0-9a-f][0-9a-f][0-9a-f][0-9a-f]%-[0-9a-f][0-9a-f][0-9a-f][0-9a-f]%-[0-9a-f][0-9a-f][0-9a-f][0-9a-f]%-[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]') then
      recheck_urls[url] = true
    end
  end

  local function checknewurl(newurl)
    if string.match(newurl, "^https?://") then
      check(newurl)
    elseif string.match(newurl, "^//") then
      check("http:"..newurl)
    elseif string.match(newurl, "^/") then
      check(string.match(url, "^(https?://[^/]+)")..newurl)
    end
  end

  local function checknewshorturl(newurl)
    if not (string.match(newurl, "^https?://") or string.match(newurl, "^/") or string.match(newurl, "^javascript:") or string.match(newurl, "^mailto:") or string.match(newurl, "^%${")) then
      check(string.match(url, "^(https?://.+/)")..newurl)
    end
  end

  for newurl, _ in pairs(recheck_urls) do
    check(newurl)
  end
  
  if string.match(url, "^https?://[^/]*friendsreunited%.co") then
    html = read_file(file)
    for newurl in string.gmatch(html, '([^"]+)') do
      checknewurl(newurl)
    end
    for newurl in string.gmatch(html, "([^']+)") do
      checknewurl(newurl)
    end
    for newurl in string.gmatch(html, ">([^<]+)") do
      checknewurl(newurl)
    end
    for newurl in string.gmatch(html, "href='([^']+)'") do
      checknewshorturl(newurl)
    end
    for newurl in string.gmatch(html, 'href="([^"]+)"') do
      checknewshorturl(newurl)
    end
    if string.match(url, "https?://[^/]*friendsreunited%.co[^/]+/[^/]+/Memory/[^%?]*%?nullableid=") then
      local newurl = string.gsub(url, "(https?://[^/]*friendsreunited%.co[^/]+)/([^/]+)/Memory/[^%?]*%?nullableid=(.+)", "%1/Media?nullableid=%3&friendly=%2")
      if downloaded[newurl] ~= true and addedtolist[newurl] ~= true then
        addedtolist[newurl] = true
        table.insert(urls, { url=newurl })
      end
    end
    if string.match(url, "https?://[^/]*friendsreunited%.co[^/]+/Memory/[^%?]*%?nullableid=") then
      local newurl = string.gsub(url, "(https?://[^/]*friendsreunited%.co[^/]+)/Memory/[^%?]*%?nullableid=", "%1/Media?nullableid=")
      if downloaded[newurl] ~= true and addedtolist[newurl] ~= true then
        addedtolist[newurl] = true
        table.insert(urls, { url=newurl })
      end
    end
    if string.match(url, "page=[0-9]+") then
      pagenum = string.match(url, "page=([0-9]+)")
      for num=1,pagenum do
        check(string.gsub(url, "page="..pagenum, "page="..num))
      end
    end
  end

  return urls
end
  

wget.callbacks.httploop_result = function(url, err, http_stat)
  -- NEW for 2014: Slightly more verbose messages because people keep
  -- complaining that it's not moving or not working
  status_code = http_stat["statcode"]
  
  url_count = url_count + 1
  io.stdout:write(url_count .. "=" .. status_code .. " " .. url["url"] .. ".  \n")
  io.stdout:flush()

  if (status_code >= 200 and status_code <= 399) then
    if string.match(url.url, "https://") then
      local newurl = string.gsub(url.url, "https://", "http://")
      downloaded[newurl] = true
    else
      downloaded[url.url] = true
    end
  end

  if string.gsub('-', '%-', '%%%-') ~= '%-' then
    return wget.actions.ABORT
  end

  if string.match(url["url"], '/Home/Login') then
    io.stdout:write("You have lost your session cookies! ABORTING\n")
    io.stdout:flush()
    return wget.actions.ABORT
  end
  
  if status_code >= 500 or
    (status_code >= 400 and status_code ~= 404) or
    status_code == 0 then
    io.stdout:write("Server returned "..http_stat.statcode.." ("..err.."). Sleeping.\n")
    io.stdout:flush()
    os.execute("sleep 1")
    tries = tries + 1
    if tries >= 5 then
      io.stdout:write("\nI give up...\n")
      io.stdout:flush()
      tries = 0
      if string.match(url["url"], "^https?://[^/]*friendsreunited%.co") or string.match(url["url"], "https?://[^/]*assetstorage%.co%.uk") then
        return wget.actions.ABORT
      else
        return wget.actions.EXIT
      end
    else
      return wget.actions.CONTINUE
    end
  end

  tries = 0

  local sleep_time = 0

  if sleep_time > 0.001 then
    os.execute("sleep " .. sleep_time)
  end

  return wget.actions.NOTHING
end

wget.callbacks.finish = function(start_time, end_time, wall_time, numurls, total_downloaded_bytes, total_download_time)
  local usersfile = io.open(item_dir..'/'..warc_file_base..'_data.txt', 'w')
  local templist = {}
  for url, _ in pairs(profiles) do
    if templist[url] ~= true then
      templist[url] = true
      usersfile:write(url.."\n")
    end
  end
  usersfile:close()
end
