import socket, time, dht, machine, ntptime
import ujson, gc, config
from machine import WDT

print("ESP32 KOMBI MAIN ÇALIŞIYOR")

wdt = WDT(timeout=15000)

# ---------- TIME ----------
try:
    ntptime.settime()
except:
    pass

def get_time_hm():
    t = time.localtime()
    return "{:02d}:{:02d}".format(t[3], t[4])

def is_day():
    h = time.localtime()[3]
    return config.DAY_START_HOUR <= h < config.DAY_END_HOUR

# ---------- SENSOR ----------
sensor = dht.DHT22(machine.Pin(config.DHT_PIN))

def read_dht():
    try:
        sensor.measure()
        return round(sensor.temperature(),1), round(sensor.humidity(),1)
    except:
        return None, None

# ---------- RELAY LOGIC ----------
def decide(temp):
    if is_day():
        if temp < config.DAY_TEMP_MIN: return "OPEN"
        if temp > config.DAY_TEMP_MAX: return "CLOSE"
    else:
        if temp < config.NIGHT_TEMP_MIN: return "OPEN"
        if temp > config.NIGHT_TEMP_MAX: return "CLOSE"
    return "KEEP"

# ---------- CACHE ----------
cache = {
    "temperature": None,
    "humidity": None,
    "relay": "UNKNOWN",
    "timestamp": "00:00"
}

last_read = 0

# ---------- SERVER ----------
addr = socket.getaddrinfo("0.0.0.0", config.SERVER_PORT)[0][-1]
s = socket.socket()
s.bind(addr)
s.listen(1)
s.settimeout(2)

print("HTTP SERVER HAZIR")

# ---------- LOOP ----------
while True:
    wdt.feed()
    now = time.time()

    if now - last_read >= config.READ_INTERVAL:
        t, h = read_dht()
        if t is not None:
            cache.update({
                "temperature": t,
                "humidity": h,
                "relay": decide(t),
                "timestamp": get_time_hm()
            })
            print("CACHE:", cache)
        last_read = now

    try:
        conn, addr = s.accept()
        conn.recv(1024)
    except OSError:
        continue

    try:
        body = ujson.dumps(cache)
        conn.send(
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: application/json\r\n"
            "Connection: close\r\n"
            "Content-Length: {}\r\n\r\n{}".format(len(body), body)
        )
    finally:
        conn.close()
        gc.collect()
