from machine import UART, Pin, Timer, ADC
import time
import uerrno

NOTIFY_URL = '' # 填入推送通知的链接(注意最后带 / ), 如 Bark 的 http://api.day.app/TX72mvgBTSoGqy5F/
JUST_NOTIFY = False # 如果为 True 则仅使用通知不使用 MQTT, 会缺少 电量查询/定位/关闭通知 等功能, 但同时节约电量
# 如果只需要通知功能, 或者为了省电, 只需要填写 NOTIFY_URL
# 并且 JUST_NOTIFY = True
# 此时下面的项目不需要填写

MQTT_URL = 'broker.emqx.io' # 公共的 MQTT 服务器, [唯一ID] 一定要自己重设, 或者为了安全可以换用自己的服务器
MQTT_PORT = 1883 # 端口
MQTT_USERNAME = '' # 用户名 (公共服务器不需要填)
MQTT_PASSWORD = '' # 密码 (功能服务器不需要填)

UNIID = 'acucxbse7wer2392nsdfusdv' # 唯一ID, 随便敲一些字符就行, 主要是公共服务器会订阅有冲突问题
LBS_API = '' # 高德开静态地图定位API, 用自己的API
# 以下为代码部分, 到此配置完全结束

def read_ini(filename):
    config = {}
    current_section = None

    try:
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(';') or line.startswith('#'):
                    continue
                if line.startswith('[') and line.endswith(']'):
                    current_section = line[1:-1]
                    config[current_section] = {}
                elif '=' in line and current_section:
                    key, value = line.split('=', 1)
                    config[current_section][key.strip()] = value.strip()
        return config

    except OSError as e:
        if e.args[0] == uerrno.ENOENT:
            return None
        else:
            raise

config = read_ini('config.ini')
if config is not None:
    ret = config['main_config']['lbs_api']
    if len(ret) > 0:
        LBS_API = ret
    ret = config['main_config']['uniid']
    if len(ret) > 0:
        UNIID = ret
    ret = config['main_config']['notify_url']
    if len(ret) > 0:
        NOTIFY_URL = ret


class ML307R_MQTT_HTTP(object):
    def __init__(self,rx,tx,u_num=0):
        self.uart=UART(u_num,115200,rx=Pin(rx),tx=Pin(tx),rxbuf=2048,txbuf=2048)
        self.rx_reading = False
        time.sleep(1)
        self.timer = Timer(-1)
        self.cb_funcs = {}
        self.header=[]
        self.network_ready()

    def start_rx_server(self):
        self.rx_reading = True
        self.timer.init(period=1000, mode=Timer.PERIODIC, callback=self.rx_server)

    def stop_rx_server(self):
        self.timer.deinit()
        self.rx_reading = False

    def rx_server(self, data) -> None:
        ret = self.uart.read()
        if ret is not None:
            print(ret.decode())

        ret = self.at_command('MQTTREAD','0')
        if ret is not None:
            parts = ret.split(b',')
            msg_count = int(parts[1].decode())
            while msg_count > 0:
                ret = self.at_command('MQTTREAD','0,1')
                if ret is None:
                    return
                msgs = ret.split(b',')
                topic = msgs[2][1:-1].decode()
                if topic in self.cb_funcs:
                    self.cb_funcs[topic](msgs[4])

                msg_count = msg_count - 1

    def at_sender(self, dat, t = 1) -> (bytes | None):
        rx_server_status = self.rx_reading
        if rx_server_status:
            self.stop_rx_server()
        
        if dat:
            self.uart.write('AT+' + dat + '\r\n')
            # print('AT+' + dat + '\r\n')
        
        ret = None
        if t != 0:
            time.sleep(0.1 * t)
            ret = self.uart.read()

        if rx_server_status:
            self.start_rx_server()
        return ret
    
    def at_command(self, cmd, var = '', t = 1) -> (bytes | None):
        ret = self.at_sender(cmd + '=' + var, t)
        if ret is None:
            return None
        if ret.find(cmd.encode()) != -1:
            val = ret[ret.find(cmd.encode()) + len(cmd.encode()) + 2:]
            val = val[:val.find(b'\r\n')]
            return val

    def at_wait_command(self, key):
        rx_server_status = self.rx_reading
        if rx_server_status:
            self.stop_rx_server()

        while True:
            ret = self.uart.read()
            val = None
            if ret is not None:
                if ret.find(key.encode()) != -1:
                    val = ret[ret.find(key.encode()) + len(key.encode()) + 2:]
                    val = val[:val.find(b'\r\n')]
                    break
            time.sleep(0.1)

        if rx_server_status:
            self.start_rx_server()
        return val
    
    def mqtt_waitURC(self):
        return self.at_wait_command('MQTTURC')
    
    def network_ready(self):
        print("[INFO] wait network")
        while True:
            ret = self.at_sender('CEREG?')
            if ret is not None:
                # print(ret)
                if b'CEREG: 0,1' in ret:
                    print("[INFO] network ready")
                    return
            time.sleep(0.5)

    def mqtt_link(self):
        print("[INFO] mqtt link")
        ret = self.at_command('MQTTSTATE','0')
        if ret is None:
            return

        if int(ret.decode()) == 2:
            self.at_command('MQTTDISC','0')

        self.at_command('MQTTCFG', '"cached",0,1')

        login_msg = ''
        if len(MQTT_USERNAME) > 0:
            login_msg = ',' + MQTT_USERNAME + ',' + MQTT_PASSWORD
        self.at_command('MQTTCONN','0,"' + MQTT_URL +'",' + str(MQTT_PORT) +',"' + UNIID +'"' + login_msg, 0)
        print("[URC]" , self.mqtt_waitURC())

        self.start_rx_server()

        self.at_command('MLPMCFG','"sleepmode",2,0')
        self.at_command('MLPMCFG','"delaysleep",2')
        time.sleep(0.5)

    def mqtt_sub(self, topic, cb):
        print("[INFO] submit topic: " + topic)
        self.at_command('MQTTSUB','0,"' + topic + '",0', 0)
        print("[URC]" , self.mqtt_waitURC())
        self.cb_funcs[topic] = cb
    
    def mqtt_publish(self, topic, qos, text):
        msg = '0,' + topic + ',' + str(qos) + ',0,0,' + str(len(text)) + ',"' + text + '"'
        # print('[SEND MSG] ', msg)
        self.at_command('MQTTPUB', msg)

    def get_response(self,info):
        nx=info.split(b'MHTTPURC: "content"')
        rep_1=nx[1].split(b",")
        rep=b"".join(rep_1[5:])
        return rep
    
    def get_url(self,url_1,url_2,t=15):
        self.at_sender('MHTTPCREATE="'+url_1+'"')
        info=self.at_sender('MHTTPREQUEST=0,1,0,"'+url_2+'"',t)
        self.at_sender('MHTTPHEADER=0')
        return self.get_response(info)
    
    def get_url_ssl(self,url_1,url_2,t=15):
        self.at_sender('MHTTPCREATE="'+url_1+'"')
        self.at_sender('MHTTPCFG="ssl",0,1,1')
        info=self.at_sender('MHTTPREQUEST=0,1,0,"'+url_2+'"',t)
        self.at_sender('MHTTPHEADER=0')
        return self.get_response(info)
    
    def make_url(self,url):
        url_1="/".join(url.split("/")[0:3])
        url_2="/"+"/".join(url.split("/")[3:])
        return [url_1,url_2]
    
    def get(self,url):
        ua=self.make_url(url)

        if "https" in ua[0]:
            ba=self.get_url_ssl(ua[0],ua[1])
        else:
            ba=self.get_url(ua[0],ua[1])
        return ba

class Bike_Dog(object):
    def __init__(self):
        self.network_module = ML307R_MQTT_HTTP(1,0)
        self.trig = Pin('GP2', Pin.IN)
        self.trig_stat = False
        self.last_call_time = time.ticks_ms()  # 初始化时间
        self.shake_monitor_start()

        if JUST_NOTIFY:
            return

        self.network_module.mqtt_link()
        self.network_module.mqtt_publish(UNIID +'-online', 0, 'online')

        self.network_module.mqtt_sub(UNIID +'-switch-shake', self.cb_shake_change)
        self.network_module.mqtt_sub(UNIID +'-get-lbs', self.cb_LBS)

        self.battery = ADC(26)
        self.cb_BT()
        self.network_module.mqtt_sub(UNIID +'-get-battery', self.cb_BT)

    def cb_shake_change(self, *args):
        if self.trig_stat:
            self.shake_monitor_stop()
        else:
            self.shake_monitor_start()
    
    def cb_BT(self, *args):
        bt_per = (self.battery.read_u16() / 65535.0) * 100
        self.network_module.mqtt_publish(UNIID +'-req-battery', 0, str(bt_per))
        if bt_per < 74:
            self.network_module.get(NOTIFY_URL + "自行车看门狗/电池电量低")


    def cb_LBS(self, *args):
        # print('[INFO] get LBS')
        self.network_module.at_command('MLBSCFG', '"method",40')
        self.network_module.at_command('MLBSCFG', '"nearbtsen",1')
        self.network_module.at_command(cmd = 'MLBSLOC', t=0)
        locate = self.network_module.at_wait_command('MLBSLOC')
        print("[INFO] LBS return: ", locate)
        if int(locate[:3].decode()) == 100:
            gps = locate[4:].decode()
            map_url = 'https://restapi.amap.com/v3/staticmap?location=' \
                + gps + '&zoom=15&size=600*600&markers=mid,,A:' + gps + \
                '&key=' + LBS_API
            self.network_module.mqtt_publish(UNIID +'-req-lbs', 0, map_url)
        else:
            self.network_module.mqtt_publish(UNIID +'-req-lbs', 0, "lbs get error, pls retry -> " + locate.decode())

    def shake_monitor_start(self):
        self.trig.irq(trigger=Pin.IRQ_RISING, handler=self.trig_callback)
        self.trig_stat = True
        self.network_module.get(NOTIFY_URL + "自行车看门狗/震动检测开启")

    def shake_monitor_stop(self):
        self.trig.irq(None)
        self.trig_stat = False
        self.network_module.get(NOTIFY_URL + "自行车看门狗/震动检测关闭")


    def trig_callback(self, trig: Pin):
        # print(time.ticks_ms())
        current_time = time.ticks_ms()
        diff = time.ticks_diff(current_time, self.last_call_time)
        
        if diff > 3000:
            self.last_call_time = current_time
            print("[INFO] detect shake")
            # clock = mm.command('AT+CCLK?').decode('utf-8').split('"')[1].split(',')[1].split('+')[0]
            self.network_module.get(NOTIFY_URL + "自行车看门狗/检测到震动")


print('[INFO] your uniid: ' + UNIID)
print('[INFO] your lbs_api: ' + LBS_API)

bd = Bike_Dog()

while True:
    time.sleep(3)
    
