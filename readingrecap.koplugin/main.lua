local WidgetContainer = require("ui/widget/container/widgetcontainer")
local UIManager = require("ui/uimanager")
local ConfirmBox = require("ui/widget/confirmbox")
local TextViewer = require("ui/widget/textviewer")
local InfoMessage = require("ui/widget/infomessage")
local LuaSettings = require("luasettings")
local DataStorage = require("datastorage")
local json = require("rapidjson")
local util = require("util")
local logger = require("logger")
local Recap = WidgetContainer:extend{ name = "readingrecap" }

local function readJSON(path)
    local file = io.open(path, "rb")
    if not file then return nil end
    local data = file:read("*a")
    file:close()
    local ok, result = pcall(json.decode, data)
    if ok and type(result) == "table" then return result end
end

function Recap:init()
    if not self.ui.document then return end
    self.base = DataStorage:getSettingsDir()
    self.settings = LuaSettings:open(self.base .. "/reading_recap.lua")
    self.ui.menu:registerToMainMenu(self)
end

function Recap:bookID()
    local id = self.ui.doc_settings and self.ui.doc_settings:readSetting("partial_md5_checksum")
    if type(id) == "string" and id:match("^%x+$") and #id == 32 then return id end
end

function Recap:loadRecap()
    local id = self:bookID()
    self.recap = id and readJSON(self.base .. "/reading_recaps/" .. id .. ".json") or nil
    if self.recap and (self.recap.book_id ~= id or type(self.recap.text) ~= "string"
        or type(self.recap.cutoff) ~= "string" or type(self.recap.id) ~= "string") then self.recap = nil end
end

function Recap:safePosition()
    local doc = self.ui.document
    if not self.recap or self:bookID() ~= self.recap.book_id
        or not doc.compareXPointers or not doc.getXPointer then return false end
    local ok, comparison = pcall(function()
        return doc:compareXPointers(self.recap.cutoff, doc:getXPointer())
    end)
    return ok and type(comparison) == "number" and comparison >= 0
end

function Recap:showRecap()
    if not self:safePosition() then
        UIManager:show(InfoMessage:new{ text = "Keine passende Rückblende für diese Lesestelle. Eine spätere Rückblende bleibt zum Schutz vor Spoilern verborgen." })
        return
    end
    UIManager:show(TextViewer:new{
        title = (self.recap.title or "Leserückblick") .. " – Was bisher geschieht",
        text = self.recap.text,
    })
end

function Recap:offer(manual)
    self:loadRecap()
    if not self:safePosition() then
        if manual then self:showRecap() end
        return
    end
    local id = self:bookID()
    local state = self.settings:readSetting(id, {})
    if not manual and state.offered == self.recap.id then return end
    state.offered = self.recap.id
    self.settings:saveSetting(id, state)
    self.settings:flush()
    UIManager:show(ConfirmBox:new{
        text = "Ein Rückblick bis zu deinem zuletzt übertragenen Lesestand ist bereit. Möchtest du ihn lesen?",
        ok_text = "Rückblick lesen", cancel_text = "Weiterlesen",
        ok_callback = function() self:showRecap() end,
    })
end

function Recap:exportRequest()
    local id = self:bookID()
    local doc = self.ui.document
    local file = doc.file or ""
    if not self.dirty or not id or not file:lower():match("%.epub$")
        or file:find("/Wiki%-Lesestoff/") then return end
    local ok, err = pcall(function()
        if not doc.getPageXPointer or not doc.getTextFromXPointers then error("Text export not supported") end
        local cutoff = doc:getXPointer()
        local start = doc:getPageXPointer(1)
        local order = doc:compareXPointers(start, cutoff)
        if type(order) ~= "number" or order < 0 then error("Invalid text boundary") end
        local text = doc:getTextFromXPointers(start, cutoff)
        if type(text) ~= "string" or #text > 16000000 then error("Invalid/oversized text export") end
        local props = self.ui.doc_props or {}
        local request = {
            version = 1, book_id = id, title = props.title or file,
            cutoff = cutoff, text = text, activity = self.activity,
            opened = self.opened, session = self.session,
        }
        local dir = self.base .. "/reading_recap_requests"
        util.makePath(dir)
        local path = dir .. "/" .. id .. ".json"
        local encoded = assert(json.encode(request))
        local out = assert(io.open(path .. ".tmp", "wb"))
        local wrote, write_err = out:write(encoded)
        local closed, close_err = out:close()
        assert(wrote, write_err)
        assert(closed, close_err)
        assert(os.rename(path .. ".tmp", path))
        self.dirty = false
    end)
    if not ok then logger.warn("Reading recap export failed:", err) end
end

function Recap:touch()
    if not self.settings then return end
    self.activity = os.time()
    self.dirty = true
end

function Recap:checkOnOpen()
    if not self.settings then return end
    self.opened = os.time()
    local id = self:bookID()
    if id then
        local state = self.settings:readSetting(id, {})
        state.session = (state.session or 0) + 1
        self.session = state.session
        self.settings:saveSetting(id, state)
        self.settings:flush()
    end
    self:touch()
    UIManager:nextTick(function()
        self:offer(false)
        self:exportRequest()
    end)
end

function Recap:onReaderReady() self:checkOnOpen() end
function Recap:onResume() self:checkOnOpen() end
function Recap:onPageUpdate() self:touch() end
function Recap:onSaveSettings()
    if self.settings then self:exportRequest() end
end
Recap.onSuspend = Recap.onSaveSettings
Recap.onCloseDocument = Recap.onSaveSettings

function Recap:addToMainMenu(menu_items)
    menu_items.reading_recap = {
        text = "Rückblick lesen", callback = function() self:offer(true) end,
    }
end

return Recap
