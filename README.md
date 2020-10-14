# wechat history export

MAC微信聊天记录导出为jsonlines。

**目前仅支持macOS**

## demo

提供了一个demo，在`demo.py`，

## 依赖

[pysqlcipher](https://github.com/leapcode/pysqlcipher)。
安装方式：```brew install pysqlcipher```

## 流程
首先，在MAC的微信中复制所需的DB数据库，通过一些方式获取AES密匙进行解密，然后去对应的数据库提取聊天记录。

## 使用方法


### 1. AES Key 获取

- 打开微信客户端, **先不要登录**
- 在Terminal中输入`lldb -p $(pgrep WeChat)`
    - `br set -n sqlite3_key`
    - `continue`
- 登录
- 返回Terminal中输入 `memory read --size 1 --format x --count 32 $rsi`
- 上边打印的即为256-bit的aes key

你会看到类似如下的输出
```
0x60000243xxxx: 0xe8 0x8d 0x4a 0xd0 0x82 0x6a 0xe2 0x8f
0x60000243xxxx: 0x77 0x70 0x54 0xd4 0x8e 0x72 0x3a 0x1b
0x60000243xxxx: 0x0a 0xe7 0x9c 0x89 0x5f 0x49 0xb0 0xec
0x60000243xxxx: 0x79 0xdf 0x2a 0x68 0xd5 0x9c 0xb8 0xf5
```

去除掉"："前面的数字字母，去掉剩余的0x，得到AES密匙。这个是不会变化的。
`'e88d4ad0826ae28f777054d48e723a1b0ae79c895f49b0ec79df2a68d59cb8f5'`。

### 2. 新建.env文件
文件中需要提供WECHAT_ROOT、WECHAT_RAW_KEY和NAME。
其中WECHAT_ROOT是微信的根目录，需要注意的是替换"2.0b4.0.9"为你自己的版本。替换"1a2b3c6dg531d"为自己的账户目录。
其中WECHAT_RAW_KEY就是刚刚获得AES密匙。
其中NAME为微信号。

```
WECHAT_ROOT = '~/Library/Containers/com.tencent.xinWeChat/Data/Library/Application Support/com.tencent.xinWeChat/2.0b4.0.9/1a2b3c6dg531d'
WECHAT_RAW_KEY = 'e88d4ad0826ae28f777054d48e723a1b0ae79c895f49b0ec79df2a68d59cb8f5'
NAME = "Imsample"
```

### 3. 运行代码

```sh
python demo.py
```
会生成一个history_{微信号}.jsonl。

## 备注

仅仅是一个DEMO，还有很多需要改进的地方。

