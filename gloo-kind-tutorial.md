# Microsserviços com Gloo API Gateway e Kind

Nesse tutorial, iremos explorar algumas das funcionalidades do Gloo[link], um API Gateway construído em cima do proxy Envoy[link]. Por ser um API Gateway, Gloo é bastante útil no contexto de microsserviços, pois é capaz de nos fornecer uma única entrada para todos os nossos serviços, melhorando a comunicação dos clientes aos serviços de várias formas[link] e outras funcionalidades como rate limiting, circuit breaking, autenticação e autorização externa, transformação de requisição e resposta, e mais. 

Como Gloo foi pensado para ser utilizado em um ambiente Kubernetes[link], estaremos utilizando uma ferramenta chamada Kind[link] para simular esse ambiente na sua máquina local.

Para seguir este tutorial, você precisará ter instalado em sua máquina as seguintes ferramentas:

* Docker [https://docs.docker.com/get-docker/]
* Kubectl [https://kubernetes.io/docs/tasks/tools/install-kubectl/]
* Kind [https://kind.sigs.k8s.io/]
* Glooctl [https://github.com/solo-io/glooctl]

Todos os arquivos criados neste tutorial podem ser encontrados neste repositório[link].

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

Após rodar os comandos acima, podemos checar se a instalação foi o sucesso rodando o seguinte comando:

`kubectl get all -n gloo-system`

Esse comando, por sua vez, deve retornar a seguinte saída:

```
NAME                                READY     STATUS    RESTARTS   AGE
pod/discovery-f7548d984-slddk       1/1       Running   0          5m
pod/gateway-5689fd59d7-wsg7f        1/1       Running   0          5m
pod/gateway-proxy-9d79d48cd-wg8b8   1/1       Running   0          5m
pod/gloo-5b7b748dbf-jdsvg           1/1       Running   0          5m

NAME                    TYPE           CLUSTER-IP      EXTERNAL-IP   PORT(S)                     AGE
service/gateway         ClusterIP      10.0.180.15     <none>        443/TCP                     5m
service/gateway-proxy   LoadBalancer   10.97.232.107   <pending>     80:30221/TCP,443:32340/TCP  5m
service/gloo            ClusterIP      10.100.64.166   <none>        9977/TCP,9988/TCP,9966/TCP  5m

NAME                            READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/discovery       1/1     1            1           5m
deployment.apps/gateway         1/1     1            1           5m
deployment.apps/gateway-proxy   1/1     1            1           5m
deployment.apps/gloo            1/1     1            1           5m

NAME                                      DESIRED   CURRENT   READY     AGE
replicaset.apps/discovery-f7548d984       1         1         1         5m
replicaset.apps/gateway-5689fd59d7        1         1         1         5m
replicaset.apps/gateway-proxy-9d79d48cd   1         1         1         5m
replicaset.apps/gloo-5b7b748dbf           1         1         1         5m

NAME                        COMPLETIONS   DURATION   AGE
job.batch/gateway-certgen   1/1           14s        5m
```

Feito isso, você agora está com o Gloo instalado no cluster que você criou. Os pods[link] `discovery`, `gateway`, `gateway-proxy` e `gloo` que se encontram no namespace[link] gloo-system, juntos, permitem que nós utilizemos o Envoy para rotear as requisições para os serviços corretos de forma fácil e com várias funcionalidades, que veremos a seguir.

## Explorando algumas das funcionalidades do Gloo

Para começarmos a testar algumas das funcionalidades do Gloo, vamos subir um serviço básico de uma API de um site de viagens para servir de exemplo. Esse serviço possui o seguinte código:

```python
import http.server
import socketserver
import json 

class Server(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        path = self.path
        print(path, flush = True)
        if path.startswith("/api/travels/1"):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(bytes(json.dumps({ 'id': 1, 'price': '3200' }).encode('utf-8')))
        else:
            self.send_response(404)
            self.end_headers()

            
def serve_forever(port):
    print("Listening on " + str(port), flush = True)
    socketserver.TCPServer(('', port), Server).serve_forever()

if __name__ == "__main__":
    serve_forever(8080)
```

O código acima instancia um servidor Python que ao ser acessado na rota `GET /api/travels/1` retorna `{ 'id': 1, 'price': '3200' }` como resposta. Caso seja acessado em uma outra rota, retorna o status de 404.

Para ser possível instanciar esse código em nosso ambiente Kubernetes, precisamos criar uma imagem Docker, que será a imagem que rodará em nossos pods dentro do Kubernetes. Para a simplicidade desse tutorial, iremos disponibilizar uma imagem do serviço descrito acima[link].

Para conseguirmos instanciar nosso serviço dentro do Kubernetes, precisamos definir um Deployment[link] e um Service[link] para a aplicação. Isso pode ser feito criando um arquivo `configuration.yml` a seguir:

```yml
apiVersion: apps/v1
kind: Deployment
metadata:
  labels:
    app: travel-api
  name: travel-api
  namespace: default
spec:
  selector:
    matchLabels:
      app: travel-api
  replicas: 1
  template:
    metadata:
      labels:
        app: travel-api
    spec:
      containers:
      - image: lucasbarross/travel-api:latest
        name: travel-api
        ports:
        - containerPort: 8080
          name: http
---
apiVersion: v1
kind: Service
metadata:
  name: travel-api
  namespace: default
  labels:
    service: travel-api
spec:
  ports:
  - port: 8080
    protocol: TCP
  selector:
    app: travel-api
```

O mais importante de se notar aqui é que o Deployment é responsável por indicar qual imagem Docker nossos pods irão baixar e executar (lucasbarross/travel-api), enquanto o Service indicará em qual porta nosso serviço irá escutar (nesse caso, 8080, já que é a que colocamos no código Python).

Feito isso, vamos aplicar essas configurações em nosso cluster Kubernetes, rodando o seguinte comando:

`kubectl apply -f configuration.yml`

Para verificar se tudo deu certo, rode o comando

`kubectl get pods`

E deve ser retornado algo parecido com:

```
NAME                          READY   STATUS              RESTARTS   AGE
travel-api-666d8db574-z6pjp   0/1     ContainerCreating   0          9s
```

Quando você rodar o comando `kubectl get pods` depois de um tempo e o status mudar para "Running", signifcará que o serviço está de pé.

### Virtual Services

Agora que temos um serviço para exemplo, vamos começar a brincar com o Gloo!

O Gloo fornece um tipo de configuração chamada Virtual Service. Através dela, mapeamos rotas a serviços, fazemos transformações na requests, configuramos autenticação/autorização das rotas, entre outras configurações [link]. Vamos começar definindo a rota do nosso serviço de exemplo para que o acessemos através do Gloo. Para isso, vamos utilizar o comando:

```
glooctl add route \
  --path-prefix /api/travels \
  --dest-name default-travel-api-8080 \
```

O que o comando quer dizer é que, para toda requisição que possui o prefixo `/api/travels`, essa requisição irá para o serviço especificado no parâmetro  `--dest-name`. Para o Gloo identificar nosso serviço `travel-api`, ele utiliza o chamado Service Discovery, que permite encontrar serviços que estão no mesmo cluster. Precisamos apenas passar o endereço do serviço no formato `namespace-serviço-porta`, que em nosso caso, é namespace `default`, serviço `travel-api` e porta `8080`. Tudo isso foi configurado no arquivo `configuration.yml`.

Feito isso, podemos testar mandando uma requisição para o Gloo em uma das rotas, como:

`curl $(glooctl proxy url)/api/travels/1`

Isso deve retornar 

`{"id": 1, "price": "3200"%`                                                                                                                                                         

Sua requisição passou pelo Envoy e foi roteada para o serviço correto (nossa travel-api). Para manter o escopo desse tutorial, não iremos instanciar outros serviços, mas é possível perceber como isso se aplicaria em um contexto real de microsserviços, onde vários serviços são utilizados para retornar informações para clientes, e através do Gloo, temos essa única porta de entrada, através do virtual service, que roteia nossos serviços. Isso tudo utilizando Service Discovery, evitando os malefícios de utilização de DNS[link].

### Autenticação e autorização

É possível também, através do Gloo, configurar um servidor externo de autenticação e escolher, através do Virtual Service, quais rotas serão autenticadas. Esse servidor é apenas uma API que para toda requisição que chega, retorna 200 caso a requisição esteja autenticada, e 403 quando contrário. É possível ser criativo aqui, e criar a autenticação/autorização conforme o necessário para sua aplicação. Essa funcionalidade é muito útil, visto que podemos garantir a autenticação para todas as APIs que estão atrás do Gloo com apenas um serviço comum. Sem utilizar o API Gateway, teríamos que cuidar disso para cada API separadamente, impondo retrabalho e possíveis falhas de segurança. Para mais informações sobre como configurar o serviço de autenticação, você pode acessar a documentação do Gloo [https://docs.solo.io/gloo/latest/guides/security/auth/custom_auth/].









