# Runestone

Runestone is a personal Markdown notebook with search, wiki links, and backlinks. Notes are stored as plain Markdown files on your computer.

## Run with Docker

Install Docker, then run these commands in a terminal.

```sh
git clone https://github.com/robert86b/runestone.git
cd runestone
docker build -t runestone .
docker run --rm --name runestone -p 127.0.0.1:8096:8096 -v runestone-notes:/data/notes runestone
```

Open <http://localhost:8096>, create a note, and use `[[Note title]]` to link to another note. The `runestone-notes` volume keeps your notes when the container stops. Back up that volume to preserve your notes.

Runestone is designed for single-user local access. It has no accounts or authentication. Keep the port bound to localhost and avoid exposing it to the internet.
