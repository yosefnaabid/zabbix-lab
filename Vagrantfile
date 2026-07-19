Vagrant.configure("2") do |config|
  config.vm.box = "debian/bookworm64"
  config.vm.box_check_update = false

  config.vm.provider "virtualbox" do |vb|
    vb.linked_clone = true
  end

  config.vm.define "zbx-server" do |srv|
    srv.vm.hostname = "zbx-server"
    srv.vm.network "private_network", ip: "192.168.56.30"
    srv.vm.network "forwarded_port", guest: 80, host: 8080, id: "zabbix-ui"
    srv.vm.network "forwarded_port", guest: 8025, host: 8025, id: "mailpit-ui"

    srv.vm.provider "virtualbox" do |vb|
      vb.name   = "zbx-server"
      vb.memory = 1536
      vb.cpus   = 2
    end

    srv.vm.provision "shell", path: "provision/comun.sh"
    srv.vm.provision "shell", path: "provision/servidor.sh"
    srv.vm.provision "shell", path: "provision/correo.sh"
  end

  config.vm.define "zbx-agent01" do |ag|
    ag.vm.hostname = "zbx-agent01"
    ag.vm.network "private_network", ip: "192.168.56.11"

    ag.vm.provider "virtualbox" do |vb|
      vb.name   = "zbx-agent01"
      vb.memory = 512
      vb.cpus   = 1
    end

    ag.vm.provision "shell", path: "provision/comun.sh"
    ag.vm.provision "shell", path: "provision/agente.sh",
                    args: ["192.168.56.30"]
  end

  config.vm.define "zbx-winserver", autostart: false do |win|
    win.vm.box = "gusztavvargadr/windows-server-core"
    win.vm.communicator = "winrm"
    win.vm.boot_timeout = 600
    win.vm.hostname = "zbx-winserver"
    win.vm.network "private_network", ip: "192.168.56.12"

    win.vm.provider "virtualbox" do |vb|
      vb.name   = "zbx-winserver"
      vb.gui    = false
      vb.memory = 2048
      vb.cpus   = 2
    end

    win.vm.provision "shell", path: "provision/agente-windows.ps1",
                     args: ["192.168.56.30"]
  end
end
