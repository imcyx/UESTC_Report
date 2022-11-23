wget https://download-installer.cdn.mozilla.net/pub/firefox/releases/107.0/linux-x86_64/zh-CN/firefox-107.0.tar.bz2;
tar -jxf firefox-*.tar.bz2;
mv firefox /opt;
ln -s /opt/firefox/firefox /usr/local/bin/firefox;
firefox --version;
