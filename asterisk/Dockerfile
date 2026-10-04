FROM andrius/asterisk:latest

COPY pjsip.conf.template /etc/asterisk/pjsip.conf.template
COPY extensions.conf.template /etc/asterisk/extensions.conf.template
COPY rtp.conf /etc/asterisk/rtp.conf
COPY modules.conf /etc/asterisk/modules.conf
COPY logger.conf /etc/asterisk/logger.conf
COPY entrypoint.sh /usr/local/bin/gemini-yemot-entrypoint.sh
RUN chmod +x /usr/local/bin/gemini-yemot-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/gemini-yemot-entrypoint.sh"]
