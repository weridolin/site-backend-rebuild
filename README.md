# site-backend-rebuild
整合了个人网站所有的功能，采用微服务的形式，部分用Go实现. [直达网址](www.weridolin.cn)



## 模块划分

#### UserCenter
[用户中心](https://github.com/weridolin/site-usercenter),提供用户功能模块和权限控制模块


#### 网关
[nginx](https://github.com/weridolin/site-backend-rebuild/tree/master/gateway),集成了权限校验

#### 功能部分
##### 个人
[仓库直达](https://github.com/weridolin/werido-site-backend):分为以下几个部分:
- 主页:简单的主页展示
- 博客:暂时挂靠在[GitHub](https://weridolin.github.io/#/)上面,后期有时间会同步到网站上.
- 留言板:网站留言
- 友链:友情链接
- 更新轨迹:网站的更新轨迹
- 疯狂实验室:一些有趣的小功能

##### 疯狂实验室

- [文件中转站](https://github.com/weridolin/werido-site-backend):提供一个文件上传下载的中转地方.
- [数据生成器](https://github.com/weridolin/werido-site-backend):提供一个假数据生成的地方,目前支持整形/邮箱/IP/地址/电话等
- [毒](https://github.com/weridolin/werido-site-backend):来，喝点毒鸡汤把
- [短链接平台](https://github.com/weridolin/werido-site-backend):提供一个短链接的生成平台.
- [Api信息汇总](https://github.com/weridolin/werido-site-backend):提供一个API信息汇总的地方。脚本会定期从各大API平台获取最新的API信息,汇总并分类.不需要再去一个个查找.todo:加入更多主流API平台
- [chatGPT](https://github.com/weridolin/werido-site-backend):直接调用的OPENAI的接口，不用翻墙也能体验.因为官方接口的收费问题.暂时停用╮(╯▽╰)╭
- covid19:疫情信息每天更新.因为国家不再统计.暂时没有做下去的动力,abandon abandon

- [管理后台](https://github.com/weridolin/werido-site-backend):网站的管理后台.待完善
- oauth:按照oauth提供一个第三方用户认证的地方.待完善
- [webhook](https://github.com/weridolin/alinLab-webhook):一个webhook测试网站


#### 部署
目前采用[docker-compose](https://github.com/weridolin/site-backend-rebuild/tree/master/deploy)


#### 前端
采用的[VUE+VITE+TS](https://github.com/weridolin/site-front-new)

##### 备注
所有东西仅用于学习用,侵权告知

