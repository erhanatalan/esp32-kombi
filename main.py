import socket, time, dht, machine, ntptime
import ujson, gc, config, secret
from machine import WDT
import network

print("ESP32 SENSOR SERVER ÇALIŞIYOR")

# ---------------- WDT ----------------
wdt = WDT(timeout=15000)

# ---------------- WIFI (STATİK IP) ----------------
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    # STATİK IP
    wlan.ifconfig((
        "192.168.1.222",    # ESP32 IP
        "255.255.255.0",    # Subnet
        "192.168.1.1",      # Gateway
        "8.8.8.8"           # DNS
    ))

    if not wlan.isconnected():
        print("WiFi bağlanıyor...")
        wlan.connect(secret.WIFI_SSID, secret.WIFI_PASSWORD)
        while not wlan.isconnected():
            time.sleep(0.5)
            wdt.feed()

    print("WiFi OK:", wlan.ifconfig())

connect_wifi()

# ---------------- TIME ----------------
UTC_OFFSET = 3 * 3600  # Türkiye

def sync_time():
    """NTP ile saat senkronizasyonu"""
    for i in range(5):
        try:
            ntptime.settime()
            print("Saat NTP ile senkronize edildi")
            return True
        except:
            print("NTP başarısız, tekrar deneniyor...")
            time.sleep(1)
    # NTP başarısız olursa manuel saat at
    tm = (2025, 12, 21, 0, 20, 45, 0, 0)  # Yıl, Ay, Gün, HaftaGünü, Saat, Dakika, Saniye, ms
    machine.RTC().datetime(tm)
    print("Manuel saat ayarlandı:", tm[4], ":", tm[5])
    return False

sync_time()

def get_time_hm():
    t = time.localtime(time.time() + UTC_OFFSET)
    return "{:02d}:{:02d}".format(t[3], t[4])

# ---------------- SENSOR ----------------
sensor = dht.DHT22(machine.Pin(config.DHT_PIN))

def read_dht():
    try:
        sensor.measure()
        return round(sensor.temperature(), 1), round(sensor.humidity(), 1)
    except:
        return None, None

# ---------------- CACHE ----------------
cache = {
    "temperature": None,
    "humidity": None,
    "timestamp": "00:00"
}

last_read = 0

# ---------------- SERVER ----------------
addr = ("192.168.1.222", config.SERVER_PORT)
s = socket.socket()
s.bind(addr)
s.listen(1)
s.settimeout(2)

print("HTTP SERVER HAZIR → http://192.168.1.222:{}".format(config.SERVER_PORT))

# ---------------- LOOP ----------------
while True:
    wdt.feed()
    now = time.time()

    # Sensör okuma
    if now - last_read >= config.READ_INTERVAL:
        t, h = read_dht()
        if t is not None:
            cache.update({
                "temperature": t,
                "humidity": h,
                "timestamp": get_time_hm()
            })
            print("DATA:", cache)
        last_read = now

    # HTTP İstek
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
