#cloud-config
users:
  - default
  - name: ec2-user
    groups: docker

packages:
  - aws-cli
  - unzip
  - vim
  - awslogs

write_files:
  - owner: root:root
    path: /etc/cron.d/docker-prune
    content: |
      # Remove all images older than 7 days (168 hours)
      @daily root docker system prune -af --filter "until=168h"

  - path: /etc/awslogs/awslogs.conf
    permissions: 0644
    owner: root:root
    content: |
      [general]
      state_file = /var/lib/awslogs/agent-state

      [/var/log/dmesg]
      file = /var/log/dmesg
      log_group_name = log${environment}${state}AppServer
      log_stream_name = dmesg/{instance_id}

      [/var/log/messages]
      file = /var/log/messages
      log_group_name = log${environment}${state}AppServer
      log_stream_name = messages/{instance_id}
      datetime_format = %b %d %H:%M:%S

      [/var/log/docker]
      file = /var/log/docker
      log_group_name = log${environment}${state}AppServer
      log_stream_name = docker/{instance_id}
      datetime_format = %Y-%m-%dT%H:%M:%S.%f


  - path: /etc/init/awslogs.conf
    permissions: 0644
    owner: root:root
    content: |
      description "Configure and start CloudWatch Logs agent on Amazon ECS container instance"
      author "Amazon Web Services"
      start on stopped rc RUNLEVEL=[345]

      script
          exec 2>>/var/log/cloudwatch-logs-start.log
          set -x
          service awslogs start
          chkconfig awslogs on
      end script


bootcmd:
  - mv /etc/init/ecs.conf /etc/init/ecs.conf.disabled

runcmd:
  - curl -L https://github.com/docker/compose/releases/download/1.21.0/docker-compose-$(uname -s)-$(uname -m) -o /usr/local/bin/docker-compose
  - chmod +x /usr/local/bin/docker-compose
  - aws s3 cp s3://${zip_file_uri} /tmp/certs.zip
  - mkdir -p /etc/docker/certs
  - unzip -d /etc/docker/certs /tmp/certs.zip
  - echo 'OPTIONS="$${OPTIONS} -H unix:///var/run/docker.sock  -H 0.0.0.0:2476 --default-ulimit nofile=1024:4096 --tlsverify --tlscacert=/etc/docker/certs/ca.pem --tlscert=/etc/docker/certs/server.pem --tlskey=/etc/docker/certs/server.key"' >> /etc/sysconfig/docker
  - service docker restart