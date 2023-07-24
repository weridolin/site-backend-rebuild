## 网关+服务发现(etcd)+confd(自动更新)

网站的网关直接采取了nginx.服务发现用的etcd,为了能够做到节点注册后去自动去更新重载网关,这里引入了confd.即通过confd监听一些服务的keys.当有新节点注册或者变更时,confd自动会去更新nginx的配置文件并且自动重启nginx服务.

![nginx和服务发现](../docs/网关和服务发现.png)