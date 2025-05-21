# 爱车看门狗

基于ML307R与RP2040(树莓派Pico)实现的自行车挪动预警与定位硬件
核心功能是在检测到震动时, 向用户手机推送一条通知, 起到提醒作用.

## 软硬件展示

![](assets/01.png)

![](assets/03.png)

## 计划添加的功能

* MQTT: 离线提醒

## 功能配置

### 准备工作-设置HTTP与MQTT

#### HTTP 通知

* IOS 使用 Bark 可以获得一个 HTTP 通知链接, 把它放在 main.py 的 NOTIFY_URL 中即可
* 想要全平台兼容的话, 可以使用 Server酱 来实现通知, 自行谷歌教程

#### MQTT 设置[可选]

这个功能为**可选功能**, 不影响核心的震动提醒功能的运作, 且启用后**耗电增加**

MQTT是为了可以与设备进行交互, 目前可以实现:

* 获取设备电量
* 开启/关闭震动提醒
* 获取当前位置

服务端部分设置: 

* 如果不在意安全, 代码默认已经配置了 MQTT 公共服务器, 你只需要改一下 UNIID 即可
  * 在意安全可以自己搭建 MQTT 服务器 本教程不提供.
* 定位部分的设置, 要注册高德开发者账号, 然后申请 WEB API, 获得 key 后, 填写到 LBS_API 即可

客户端部分设置: 

* 本教程提供 IOS 版本的 MQTT 客户端方案
* 其他的方案有 MQTT 网页客户端/其他APP 本教程不提供.

### 为硬件安装固件

1. 在vscode中安装 Raspberry Pi Pico 扩展与 IntelliCode 扩展

2. 给 Pico 烧录好 MicroPython 的 uf2 固件 (自行谷歌)

3. 打开main.py, 对其进行配置

```python
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
```

4. 点击 Run 验证功能是否正常
5. 点击 All commands -> Upload Project To Pico
6. 关闭 VsCode, 设备重新上一次电, 验证功能是否正常

### 如何验证功能是否正常?

1. 设备开机会发送通知(爱车看门狗 震动检测开启), 未发送则表示有问题
2. 摇动设备会发送通知
3. 验证 MQTT 功能是否正常
   1. IOS设备使用下面章节的功能按钮来测试即可
   2. 其他平台验证 本教程不提供


## [IOS平台] 查看/设置 设备

### 快捷指令的设置

点击分享的链接获得快捷指令模版, 在 [填写你自己的UNIID] 中填写好, 验证是否有效.

改好UNIID后如图, 可以添加桌面或者负一屏 (UNIID示例取自 main.py 中的默认值):

![](assets/03.png)

### 快捷指令🔗分享

震动提醒: https://www.icloud.com/shortcuts/cb29e71f1fa84ab0826500942d10e883

查询电量: https://www.icloud.com/shortcuts/9b71ff0aa79f40c9a60abf1565f751ab

位置获取: https://www.icloud.com/shortcuts/a12aa330ff734be7917f60d623da9966



## 硬件相关说明

### 物料表

* 单片机: 树莓派 pico mini rp2040
* 4G模块: 中移ML307R-DL
  * 最好选带流量的那种
* 震动传感器: 801S 3脚 震动开关
* 电池: 规格903759  2500毫安时
* 充放电模块: 2A 5V充放电一体模块3.7V/4.2V锂电池充电升压移动电源板充放保护
  * 最好选一个没有最低电流限制的, 长出5V的, 防止电流过小自动断电



### PCB原理图:



![](assets/02.png)
