# 查询余额

> 来源：DeepSeek API 官方文档

# 查询余额


```
GET https://api.deepseek.com/user/balance
```


查询账号余额


## Responses​

- 200
OK, 返回用户余额详情

- application/json
- Schema
- Example (from schema)
- Example
Schema

is_available boolean当前账户是否有余额可供 API 调用

balance_infos

object[]

Array [

currency stringPossible values: [CNY, USD]

货币，人民币或美元

total_balance string总的可用余额，包括赠金和充值余额

granted_balance string未过期的赠金余额

topped_up_balance string充值余额

]

```
{  "is_available": true,  "balance_infos": [    {      "currency": "CNY",      "total_balance": "110.00",      "granted_balance": "10.00",      "topped_up_balance": "100.00"    }  ]}
```

```
{  "is_available": true,  "balance_infos": [    {      "currency": "CNY",      "total_balance": "110.00",      "granted_balance": "10.00",      "topped_up_balance": "100.00"    }  ]}
```

curlpythongonodejsrubycsharpphpjavapowershellCURL```bash
curl -L -X GET 'https://api.deepseek.com/user/balance' \-H 'Accept: application/json' \-H 'Authorization: Bearer <TOKEN>'
```

Request Collapse allBase URLEdithttps://api.deepseek.comAuthBearer TokenSend API RequestResponseClearClick the Send API Request button above and see the response here!

上一页列出模型下一页DeepSeek-V4 预览版：迈入百万上下文普惠时代