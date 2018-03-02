# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.require_version ">= 1.8"

Vagrant.configure(2) do |config|
  config.vm.box = "ubuntu/trusty64"

  config.vm.synced_folder "~/.aws", "/home/vagrant/.aws"

  # Need to use rsync in order to prevent a vboxfs/docker/gunicorn-related
  # file corruption issue.
  config.vm.synced_folder ".", "/vagrant",
      type: "rsync",
      rsync__exclude: [".git/",
                       "reports/",
                       "geoserver/data_dir/",
                       "django/publicmapping/publicmapping/config_settings.py",
                       "django/publicmapping/locale/"],
      rsync__args: ["--verbose", "--archive", "--delete", "-z", "--links"]

  config.vm.provider :virtualbox do |vb|
    vb.memory = 4096
    vb.cpus = 2
  end

  # Nginx
  config.vm.network :forwarded_port, guest: 8080, host: 8080

  # Change working directory to /vagrant upon session start.
  config.vm.provision "shell", inline: <<SCRIPT
    if ! grep -q "cd /vagrant" "/home/vagrant/.bashrc"; then
        echo "cd /vagrant" >> "/home/vagrant/.bashrc"
    fi
SCRIPT

  config.vm.provision "ansible" do |ansible|
      ansible.playbook = "deployment/ansible/district-builder.yml"
      ansible.galaxy_role_file = "deployment/ansible/roles.yml"
  end
end
