# Microserviçós com Gloo API Gateway e Kind

Nesse tutorial, iremos explorar algumas das funcionalidades do Gloo[https://docs.solo.io/gloo/latest], um API Gateway construído em cima do proxy Envoy[https://www.envoyproxy.io/]. Por ser um API Gateway, Gloo é bastante útil no contexto de microserviçós, pois é capaz de nos fornecer uma única entrada para todos os nossos serviços, melhorando a comunicação dos clientes aos serviços de várias formas[https://microservices.io/patterns/apigateway.html#resulting-context] e fornecendo outras funcionalidades como rate limiting, circuit breaking, autenticação e autorização, transformação de requisição e resposta, e mais. 

Como Gloo foi pensado para ser utilizado em um ambiente Kubernetes[https://kubernetes.io/], estaremos utilizando uma ferramenta chamada Kind[https://kind.sigs.k8s.io/] para simular esse ambiente na sua máquina local.

Para seguir este tutorial, você precisará ter instalado em sua máquina as seguintes ferramentas:

* Docker [https://docs.docker.com/get-docker/]
* Kubectl [https://kubernetes.io/docs/tasks/tools/install-kubectl/]
* Kind [https://kind.sigs.k8s.io/]
* Glooctl [https://docs.solo.io/gloo/latest/installation/gateway/kubernetes/#install-command-line-tool-cli]

Todos os arquivos criados neste tutorial podem ser encontrados neste repositório[https://github.com/lucasbarross/microsservices-api].

## Instalando Gloo dentro de um cluster do Kind

### Criando o cluster Kubernetes

Em um ambiente Kubernetes, precisamos criar um cluster para que nossos serviços rodem dentro dele. Podemos criá-lo facilmente com Kind, utilizando o seguinte comando em seu terminal:

```
cat <<EOF | kind create cluster --name kind --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 31500
    hostPort: 31500
    protocol: TCP
  - containerPort: 32500
    hostPort: 32500
    protocol: TCP
EOF
```

Note que, no comando, nós precisamos passar uma configuração a mais mapeando algumas portas para sua máquina. Como o Kind cria os serviços em containers Docker, essa configuração é necessária para que o Gloo consiga ser acessado a partir da sua máquina.

Após rodar o comando acima, você pode acessar o cluster que você criou utilizando o comando

`kubectl cluster-info --context kind-kind`

### Instalando o Gloo

A partir daqui, podemos utilizar a cli do Gloo, glooctl, para instanciar os componentes do Gloo:

```
cat <<EOF | glooctl install gateway --values -
gatewayProxies:
  gatewayProxy:
    service:
      type: NodePort
      httpPort: 31500
      httpsPort: 32500
      httpNodePort: 31500
      httpsNodePort: 32500
EOF
```

Note que as portas que configuramos ao criar o cluster têm que casar com as do comando acima. Essa configuração extra de mapeamento de portas não é necessário em um ambiente Kubernetes real.

### Verificando a instalação

Após rodar os comandos acima, podemos checar se a instalação foi sucesso rodando o seguinte comando:

`kubectl get all -n gloo-system`

Esse comando, por sua vez, deve retornar a seguinte saída:

```
NAME                                READY   STATUS    RESTARTS   AGE
pod/discovery-74bb9f4bdf-r84vv      1/1     Running   2          5m
pod/gateway-84445bdffb-flpsq        1/1     Running   1          5m
pod/gateway-proxy-cb55cd9f9-zdlw5   1/1     Running   1          5m
pod/gloo-6874d49974-bc4mb           1/1     Running   2          5m

NAME                    TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)                               AGE
service/gateway         ClusterIP   10.96.51.235   <none>        443/TCP                               5m
service/gateway-proxy   NodePort    10.96.237.64   <none>        31500:31071/TCP,32500:31599/TCP       5m
service/gloo            ClusterIP   10.96.253.58   <none>        9977/TCP,9988/TCP,9966/TCP,9979/TCP   5m

NAME                            READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/discovery       1/1     1            1           5m
deployment.apps/gateway         1/1     1            1           5m
deployment.apps/gateway-proxy   1/1     1            1           5m
deployment.apps/gloo            1/1     1            1           5m

NAME                                      DESIRED   CURRENT   READY   AGE
replicaset.apps/discovery-74bb9f4bdf      1         1         1       5m
replicaset.apps/gateway-84445bdffb        1         1         1       5m
replicaset.apps/gateway-proxy-cb55cd9f9   1         1         1       5m
replicaset.apps/gloo-6874d49974           1         1         1       5m

NAME                        COMPLETIONS   DURATION   AGE
job.batch/gateway-certgen   1/1           14s        5m
```

Feito isso, você agora está com o Gloo instalado no cluster que você criou. Os pods[https://kubernetes.io/docs/concepts/workloads/pods/] `discovery`, `gateway`, `gateway-proxy` e `gloo` que se encontram no namespace[https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/] `gloo-system`, juntos, permitem que nós utilizemos o Envoy para rotear as requisições para os serviços corretos de forma fácil e com várias funcionalidades, que veremos a seguir.

## Explorando algumas das funcionalidades do Gloo

Para começarmos a testar algumas das funcionalidades do Gloo, vamos cometer *overengineering* para o bem do aprendizado e iremos criar uma calculadora que possui duas APIs: uma API chamada `add-sub-api` que provê as funcionalidades de adição e subtração, e outra API chamada `multiply-division-api`, que provê as funcionalidades de multiplicação e divisão.

A `add-sub-api` provê as rotas `/add` e `/sub`, enquanto a `multiply-division-api` provê as rotas `/multiply` e `/divide`

Para ser possível instanciar essas APIs em nosso ambiente Kubernetes, precisamos criar uma imagem Docker para cada uma dessas APIs, que serão as imagens que rodarão em nossos pods dentro do Kubernetes. Para a simplicidade desse tutorial, iremos disponibilizar essas imagens aqui(https://hub.docker.com/r/zaulao/add-sub-api) e aqui (https://hub.docker.com/r/zaulao/multiply-division-api). Elas serão utilizadas abaixo.

Para conseguirmos instanciar nosso serviço dentro do Kubernetes, precisamos definir um Deployment[https://kubernetes.io/docs/concepts/workloads/controllers/deployment/] e um Service[https://kubernetes.io/docs/concepts/services-networking/service/] para cada API da aplicação. Isso pode ser feito criando um arquivo `configuration.yml` a seguir:

```yml
apiVersion: apps/v1
kind: Deployment
metadata:
  labels:
    app: add-sub-api
  name: add-sub-api
  namespace: default
spec:
  selector:
    matchLabels:
      app: add-sub-api
  replicas: 1
  template:
    metadata:
      labels:
        app: add-sub-api
    spec:
      containers:
      - image: zaulao/add-sub-api
        name: add-sub-api
        ports:
        - containerPort: 5000
          name: http
---
apiVersion: v1
kind: Service
metadata:
  name: add-sub-api
  namespace: default
  labels:
    service: add-sub-api
spec:
  ports:
  - port: 5000
    protocol: TCP
  selector:
    app: add-sub-api
---
apiVersion: apps/v1
kind: Deployment
metadata:
  labels:
    app: multiply-division-api
  name: multiply-division-api
  namespace: default
spec:
  selector:
    matchLabels:
      app: multiply-division-api
  replicas: 1
  template:
    metadata:
      labels:
        app: multiply-division-api
    spec:
      containers:
      - image: zaulao/multiply-division-api
        name: multiply-division-api
        ports:
        - containerPort: 5001
          name: http-auth
---
apiVersion: v1
kind: Service
metadata:
  name: multiply-division-api
  namespace: default
  labels:
    service: multiply-division-api
spec:
  ports:
  - port: 5001
    protocol: TCP
  selector:
    app: multiply-division-api
```

O mais importante de se notar aqui é que o Deployment é responsável por indicar qual imagem Docker nossos pods irão baixar e executar, enquanto o Service indicará em qual porta nosso serviço irá escutar (nesse caso, as portas estão indicadas no código das nossas APIs).

Após criar o arquivo, vamos aplicar essas configurações em nosso cluster Kubernetes rodando o seguinte comando:

`kubectl apply -f configuration.yml`

Para verificar se tudo deu certo, rode o comando

`kubectl get pods`

E deve ser retornado algo parecido com:

```
NAME                                     READY   STATUS              RESTARTS   AGE
add-sub-api-79968f5d6d-vxdvc             0/1     ContainerCreating   0          39s
multiply-division-api-847bb69d9d-ldqwg   0/1     ContainerCreating   0          79s
```

Quando você rodar o comando `kubectl get pods` depois de um tempo e o status mudar para "Running", isso significa que os serviços estão de pé.

```
NAME                                     READY   STATUS    RESTARTS   AGE
add-sub-api-79968f5d6d-vxdvc             1/1     Running   0          5m50s
multiply-division-api-847bb69d9d-ldqwg   1/1     Running   0          6m30s
```

**PS**. É possível que demore cerca de alguns minutos para subir os serviços (status ficar indicado como "Running"). Tenha paciência! :P

### Virtual Services

Agora que temos um serviço para exemplo, vamos começar a brincar com o Gloo!

O Gloo fornece um tipo de configuração chamada Virtual Service. Através dela, mapeamos rotas a serviços, fazemos transformações na requests, configuramos autenticação/autorização das rotas, entre outras configurações [https://docs.solo.io/gloo/latest/reference/api/github.com/solo-io/gloo/projects/gateway/api/v1/virtual_service.proto.sk/]. Vamos começar definindo uma das rotas de um dos serviços da calculadora, digitando o comando a seguir:

```
glooctl add route \
  --path-prefix /api/multdiv \
  --prefix-rewrite / \
  --dest-name default-multiply-division-api-5001
```

O comando indica que para toda requisição que possui o prefixo `/api/multdiv`, essa requisição será direcionada para o serviço especificado no parâmetro  `--dest-name`. Nós especificamos o `--dest-name` como `default-multiply-division-api-5001` porque para o Gloo identificar nosso serviço `multiply-division-api`, ele utiliza o chamado Service Discovery, que permite encontrar serviços que estão no mesmo cluster. Precisamos apenas passar o endereço do serviço no formato `namespace-serviço-porta`, que em nosso caso, é namespace `default`, serviço `multiply-division-api` e porta `5001`. Tudo isso foi configurado no arquivo `configuration.yml` que apresentamos a você na etapa anterior deste tutorial. 

Nesse comando nós também utilizamos uma das funcionalidades de gerenciamento de tráfego do Gloo, o "prefix-rewrite", que vai fazer com que toda request que chegue no serviço, ao invés de chegar no path `/api/multdiv`, chegará com o restante do path. Exemplo: `/api/multdiv/multiply` chegará como `/multiply` na api `multiply-division-api`.

Feito isso, podemos testar mandando uma requisição para o Envoy em uma das rotas. Para descobrir qual o endereço do Envoy, estaremos utilizando o valor retornado pelo comando `glooctl proxy url`. O comando da requisição deve ser parecido com:

```curl --header "Content-Type: application/json" \
  --request POST \
  --data '{"x":"10","y":"20"}' \
  $(glooctl proxy url)/api/multdiv/multiply
```

Isso deve retornar 

```{
  "Message": 200, 
  "Status code": 200
}
```                                                                                                                                                         

Sua requisição passou pelo Envoy e foi roteada para o serviço correto (multiply-division-api). Podemos adicionar agora uma rota para o serviço de adição e subtração, com um comando parecido com o anterior:

```
glooctl add route \
  --path-prefix /api/addsub \
  --prefix-rewrite / \
  --dest-name default-add-sub-api-5000
```

Para testar, basta mandar uma requisição:

```curl --header "Content-Type: application/json" \
  --request POST \
  --data '{"x":"10","y":"20"}' \
  $(glooctl proxy url)/api/addsub/add
```

E pronto, as duas APIs de nossa calculadora estão sendo expostas por uma única URL, como se fossem apenas um serviço!

Através desse exemplo, é possível perceber como isso se aplicaria em um contexto real de microserviços, onde vários serviços são utilizados para retornar informações para clientes, e através do Gloo, temos essa única porta de entrada que roteia nossas requisições para o serviço correto, facilitando bastante para o cliente da API. Outro ponto é que isso tudo é feito utilizando Service Discovery, evitando os malefícios de utilização de DNS em um ambiente efêmero como Kubernetes.

### Autenticação e autorização

É possível também, através do Gloo, configurar um servidor externo de autenticação/autorização e escolher, através do Virtual Service, quais rotas serão autenticadas/autorizadas. Esse servidor é apenas uma API que para toda requisição que chega, retorna 200 caso a requisição esteja autenticada, e 403 caso contrário. É possível ser criativo aqui, e criar a autenticação/autorização conforme o necessário para sua aplicação. Essa funcionalidade é muito útil, visto que podemos garantir a autenticação para todas as APIs que estão atrás do Gloo com apenas um serviço comum. Sem utilizar o API Gateway, teríamos que cuidar disso para cada API separadamente, impondo retrabalho e possíveis falhas de segurança. Para mais informações sobre como configurar o serviço de autenticação, você pode acessar a documentação do Gloo [https://docs.solo.io/gloo/latest/guides/security/auth/custom_auth/].

## Conclusão

Através desse tutorial, esperamos fornecer uma aplicação do padrão API Gateway e mostrar seu valor para uma arquitetura de microserviçós. Por causa disso, não ensinamos todas as funcionalidades importantes do Gloo, como processamento de requisição, observabilidade e configuração de TLS, mas seguindo esse tutorial e a documentação do Gloo, você conseguirá explorar o Gloo com facilidade. 
