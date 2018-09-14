#cloud-config
users:
  - default
  - name: ec2-user
    groups: docker

packages:
  - aws-cli
  - unzip
  - vim

write_files:
- owner: root:root
  path: /etc/cron.d/docker-prune
  content: |
    # Remove all images older than 7 days (168 hours)
    @daily root docker system prune -af --filter "until=168h"

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