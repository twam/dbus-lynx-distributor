#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
SERVICE_NAME=$(basename $SCRIPT_DIR)

# set permissions for script files
chmod 744 $SCRIPT_DIR/install.sh
chmod 744 $SCRIPT_DIR/restart.sh
chmod 744 $SCRIPT_DIR/uninstall.sh
chmod 755 $SCRIPT_DIR/service/run
chmod 755 $SCRIPT_DIR/service/log/run

mount -o remount,rw /

pip3 --version
if [ $? -gt 0 ]
then
    opkg update && \
    opkg install python3-pip
fi

# check dependencies
python -c "import usb"
if [ $? -gt 0 ]
then
    pip3 install pyusb
fi

mount -o remount,ro /

# create sym-link to run script in deamon
#ln -s $SCRIPT_DIR/service /opt/victronenergy/service/$SERVICE_NAME
ln -s $SCRIPT_DIR/service /service/$SERVICE_NAME

# add install-script to rc.local to be ready for firmware update
filename=/data/rc.local
if [ ! -f $filename ]
then
    touch $filename
    chmod 777 $filename
    echo "#!/bin/bash" >> $filename
    echo >> $filename
fi

# if not alreay added, then add to rc.local
grep -qxF "bash $SCRIPT_DIR/install.sh" $filename || echo "bash $SCRIPT_DIR/install.sh" >> $filename
