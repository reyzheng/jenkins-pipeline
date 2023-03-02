FROM jenkins/agent as agent

USER root

RUN apt-get update && apt-get install -y lsb-release
RUN apt-get install curl -y
#COPY --from=dagger /dagger/cmd/dagger/dagger /usr/local/bin/dagger
RUN curl -fsSLo /usr/share/keyrings/docker-archive-keyring.asc \
  https://download.docker.com/linux/debian/gpg
RUN echo "deb [arch=$(dpkg --print-architecture) \
  signed-by=/usr/share/keyrings/docker-archive-keyring.asc] \
  https://download.docker.com/linux/debian \
  $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list
RUN apt-get update && apt-get install -y docker-ce-cli

RUN cd /usr/local && curl -L https://dl.dagger.io/dagger-cue/install.sh | sh
RUN dagger-cue version
