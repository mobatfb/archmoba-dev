-- KOFMULTI | MAME 0.289 (kf2k2mp2), telemetria interna Neo Geo.
-- V3: PERFECT por KO (HP rival <=0 signed) o por tiempo, ganador con HP 102.
-- Una perdida de personaje puede dar COMO MAXIMO un PERFECT observado.
-- No modifica vida, timer, scores ni archivos ROM.
local output_path = os.getenv("KOF_ARENA_LUA_STATE")
if not output_path or output_path == "" then
    output_path = "KOF_ARENA_LUA_ESTADO.txt"
end

local cpu = manager.machine.devices[":maincpu"]
if cpu == nil then
    emu.print_error("KOF ARENA Lua: falta :maincpu.")
    return
end
local mem = cpu.spaces["program"]
if mem == nil then
    emu.print_error("KOF ARENA Lua: falta memoria program.")
    return
end

local HP_P1, HP_P2 = 0x108239, 0x108439
local LOST_P1, LOST_P2 = 0x10A7E5, 0x10A80B
local TIMER = 0x10A7D2
local FULL_HP = 102

local frame, seq = 0, 0
local ko_seen, perfect = {0, 0}, {0, 0}
local last_lost, last_timer, timer_zero_frame = nil, nil, nil
local last_values, last_write_frame = nil, -100
local warned_read, warned_write = false, false

local function sample()
    return mem:read_u8(HP_P1), mem:read_u8(HP_P2),
           mem:read_u8(LOST_P1), mem:read_u8(LOST_P2),
           mem:read_u8(TIMER)
end

local function terminal_hp(value)
    -- 128..255 como Byte signed son -128..-1.
    return value == 0 or value >= 128
end

local function loss_event(loser, current_hp1, current_hp2, timer)
    local winner = 3 - loser
    local winner_hp = (winner == 1) and current_hp1 or current_hp2
    local loser_hp = (loser == 1) and current_hp1 or current_hp2
    local by_ko = terminal_hp(loser_hp)
    if by_ko then
        ko_seen[loser] = ko_seen[loser] + 1
    end
    if winner_hp ~= FULL_HP then return false end

    local by_time = timer == 0 and not by_ko and loser_hp < FULL_HP and
        timer_zero_frame ~= nil and frame >= timer_zero_frame and
        frame - timer_zero_frame <= 500
    if by_ko or by_time then
        perfect[winner] = perfect[winner] + 1
        return true
    end
    return false
end

local function write_state(p1, p2, l1, l2, timer)
    seq = seq + 1
    -- Formato V3: seq, HP1, HP2, bajas1, bajas2, KO1, KO2,
    -- tiempo, PERFECT1, PERFECT2; los perfects son OBSERVACIONES.
    local line = string.format(
        "KOF_LUA_V3\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\n",
        seq, p1, p2, l1, l2, ko_seen[1], ko_seen[2], timer,
        perfect[1], perfect[2])
    local file, err = io.open(output_path, "wb")
    if not file then
        if not warned_write then
            warned_write = true
            emu.print_error("KOF ARENA Lua: telemetria no escribible: " .. tostring(err))
        end
        return
    end
    file:write(line)
    file:close()
    last_write_frame = frame
    warned_write = false
end

_G.kof_arena_health_subscription = emu.add_machine_frame_notifier(function()
    frame = frame + 1
    local ok, hp1, hp2, l1, l2, timer = pcall(sample)
    if not ok then
        if not warned_read then
            warned_read = true
            emu.print_error("KOF ARENA Lua: error leyendo RAM: " .. tostring(hp1))
        end
        return
    end
    warned_read = false

    -- Anotamos el cero en el fotograma emulado: la baja por tiempo puede
    -- materializarse cientos de fotogramas despues del cero.
    if last_timer ~= nil then
        if timer == 0 and last_timer ~= 0 then
            timer_zero_frame = frame
        elseif timer > last_timer and timer - last_timer >= 10 then
            timer_zero_frame = nil
        end
    end
    last_timer = timer

    local perfect_now = false
    if last_lost and l1 <= 3 and l2 <= 3 then
        if last_lost[1] <= 2 and l1 == last_lost[1] + 1 then
            perfect_now = loss_event(1, hp1, hp2, timer) or perfect_now
        end
        if last_lost[2] <= 2 and l2 == last_lost[2] + 1 then
            perfect_now = loss_event(2, hp1, hp2, timer) or perfect_now
        end
    end
    last_lost = {l1, l2}

    if frame % 6 ~= 0 and not perfect_now then return end
    local key = string.format("%d,%d,%d,%d,%d,%d,%d,%d,%d",
        hp1, hp2, l1, l2, ko_seen[1], ko_seen[2], timer,
        perfect[1], perfect[2])
    if last_values ~= key or frame - last_write_frame >= 30 then
        write_state(hp1, hp2, l1, l2, timer)
        last_values = key
    end
end)

_G.kof_arena_reset_subscription = emu.add_machine_reset_notifier(function()
    last_lost, last_timer, timer_zero_frame = nil, nil, nil
    last_values = nil
    -- Los contadores KO y PERFECT siguen acumulados en esta sesion MAME.
end)

emu.print_info("KOF ARENA Lua V3: PERFECT por KO/tiempo, SOLO LECTURA: " ..
    output_path)
