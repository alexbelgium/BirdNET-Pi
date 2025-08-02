ARG BUILD_FROM
FROM ${BUILD_FROM}

USER root

ADD https://raw.githubusercontent.com/alexbelgium/hassio-addons/master/.templates/ha_lsio.sh /ha_lsio.sh
ARG CONFIGLOCATION="/data"
RUN chmod 744 /ha_lsio.sh && if grep -qr "lsio" /etc; then /ha_lsio.sh "$CONFIGLOCATION"; fi && rm /ha_lsio.sh

ADD https://raw.githubusercontent.com/alexbelgium/hassio-addons/master/.templates/ha_automodules.sh /ha_automodules.sh
ADD https://raw.githubusercontent.com/alexbelgium/hassio-addons/master/.templates/ha_autoapps.sh /ha_autoapps.sh
ADD https://raw.githubusercontent.com/alexbelgium/hassio-addons/master/.templates/ha_entrypoint.sh /ha_entrypoint.sh
ADD https://raw.githubusercontent.com/alexbelgium/hassio-addons/master/.templates/ha_entrypoint_modif.sh /ha_entrypoint_modif.sh
ADD https://raw.githubusercontent.com/alexbelgium/hassio-addons/master/.templates/bashio-standalone.sh /.bashio-standalone.sh

# placeholder for remaining instructions
