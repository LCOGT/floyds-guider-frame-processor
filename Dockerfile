FROM python:3.9

RUN mkdir /home/eng && /usr/sbin/groupadd -g 500 "eng" \
        && /usr/sbin/useradd -g 500 -d /home/eng -M -N -u 500 eng \
        && chown -R eng:eng /home/eng

COPY . /lco/floyds-guider-frame-processor

RUN pip install /lco/floyds-guider-frame-processor/

USER eng

WORKDIR /home/eng
