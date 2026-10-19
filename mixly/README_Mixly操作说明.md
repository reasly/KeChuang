# RF-Nano 的 Mixly 图形化程序

两个 `.mix` 文件均为可重新打开、拖动和修改的图形化积木工程。原始范例没有被覆盖。

## 板卡与库

- Mixly：2.0 rc4 或兼容版本。
- 板卡：`Arduino AVR → Arduino Nano`。
- 需要的 Arduino 库：`RF24`、`OneWire`、`DallasTemperature`。
- 两块 RF-Nano 的无线参数必须完全一致：地址 `FRESH`、频道 `76`、速率 `1Mbps`、32字节固定载荷。

## 发送端

打开 `01_泡沫箱温度发送端_RF-Nano.mix`。程序被分成三部分：

1. 顶部声明区：RF24、温度变量、数据包和序号。
2. `sampleAndSend` 函数积木：读取 D4 的 DS18B20，校验温度，组装并发送 `BOX01,温度,序号`。
3. 主循环：每 1000ms 调用一次函数。

如果以后增加第二个泡沫箱，只需要把组包积木中的 `BOX01` 改为 `BOX02`，其余参数不变。

## 接收端

打开 `02_电脑温度接收端_RF-Nano.mix`。`receiveAndPrint` 函数收到无线数据后从 USB 串口原样输出；Python 使用 9600 波特率读取。

上传接收端后请关闭 Mixly 串口监视器，再启动 Python。两个软件不能同时占用同一个 COM 口。

## DS18B20 接线

- 红线 VCC → 5V。
- 黑线 GND → GND。
- 黄/白线 DATA → D4。
- DATA 与 5V 之间接一只 4.7kΩ 上拉电阻。

两块板的地址、频道和速率必须相同，但无线引脚不同，不能互相照搬：泡沫箱发送板是新版，使用 `RF24 radio(7,8)`（CE=D7，CSN=D8）；电脑接收板是旧版，使用 `RF24 radio(10,9)`（CE=D10，CSN=D9）。D4 给温度传感器，不和无线引脚冲突。
