use std::{
    collections::HashMap,
    env,
    fs::{self, OpenOptions},
    io::{self, Write},
    path::{Path, PathBuf},
    time::{SystemTime, UNIX_EPOCH},
};

#[derive(Debug, Clone, PartialEq, Eq)]
struct Record {
    status: char,
    kind: char,
    title: String,
    fields: Vec<(String, String)>,
    line: usize,
}
#[derive(Debug, Clone, PartialEq, Eq)]
enum Span {
    Record(Record),
    Opaque(String),
    Comment(String),
    Blank(String),
    Body(String),
}
#[derive(Debug)]
struct Document {
    spans: Vec<Span>,
}

fn quoted(input: &str) -> Result<(String, &str), String> {
    if !input.starts_with('"') {
        return Err("expected quoted value".into());
    }
    let b = input.as_bytes();
    let mut escaped = false;
    for i in 1..b.len() {
        if escaped {
            escaped = false;
            continue;
        }
        if b[i] == b'\\' {
            escaped = true;
            continue;
        }
        if b[i] == b'"' {
            return Ok((
                input[1..i].replace("\\\"", "\"").replace("\\\\", "\\"),
                &input[i + 1..],
            ));
        }
    }
    Err("unterminated quoted value".into())
}
fn tokens(mut input: &str) -> Result<Vec<String>, String> {
    let mut out = Vec::new();
    while !input.trim_start().is_empty() {
        input = input.trim_start();
        if input.starts_with('"') {
            let (v, rest) = quoted(input)?;
            out.push(v);
            input = rest;
        } else if let Some(end) = input.find(char::is_whitespace) {
            out.push(input[..end].into());
            input = &input[end..];
        } else {
            out.push(input.into());
            break;
        }
    }
    Ok(out)
}
fn parse_line(raw: &str, line: usize) -> Result<Span, String> {
    let text = raw.trim_end_matches(['\r', '\n']);
    if text.is_empty() {
        return Ok(Span::Blank(raw.into()));
    }
    if text.trim_start().starts_with('#') {
        return Ok(Span::Comment(raw.into()));
    }
    if !text.starts_with('[')
        || text.len() < 6
        || text.as_bytes()[2] != b']'
        || text.as_bytes()[3] != b' '
    {
        return Ok(Span::Body(raw.into()));
    }
    let status = text.chars().nth(1).unwrap();
    let kind = text.chars().nth(4).unwrap();
    if !matches!(status, ' ' | 'x' | 'N') || !matches!(kind, 'T' | 'E' | 'N') {
        return Ok(Span::Opaque(raw.into()));
    }
    let rest = &text[6..];
    let (title, rest) = if rest.starts_with('"') {
        quoted(rest)?
    } else {
        let end = rest.find(char::is_whitespace).unwrap_or(rest.len());
        (rest[..end].into(), &rest[end..])
    };
    if title.is_empty() {
        return Err(format!("line {line}: empty title"));
    }
    let mut fields = Vec::new();
    for token in tokens(rest)? {
        let Some(i) = token.find(':') else {
            return Err(format!("line {line}: malformed detail `{token}`"));
        };
        if i == 0 || i + 1 == token.len() {
            return Err(format!("line {line}: malformed detail `{token}`"));
        }
        fields.push((token[..i].into(), token[i + 1..].into()));
    }
    Ok(Span::Record(Record {
        status,
        kind,
        title,
        fields,
        line,
    }))
}
fn parse(source: &str) -> Result<Document, String> {
    let mut spans = Vec::new();
    for (i, line) in source.split_inclusive('\n').enumerate() {
        spans.push(parse_line(line, i + 1)?);
    }
    if !source.is_empty() && !source.ends_with('\n') && spans.is_empty() {
        spans.push(parse_line(source, 1)?);
    }
    Ok(Document { spans })
}
fn records(doc: &Document) -> Vec<&Record> {
    doc.spans
        .iter()
        .filter_map(|s| {
            if let Span::Record(r) = s {
                Some(r)
            } else {
                None
            }
        })
        .collect()
}
fn id(r: &Record) -> Option<&str> {
    r.fields
        .iter()
        .find(|(k, _)| k == "id")
        .map(|(_, v)| v.as_str())
}
fn resolve(arg: Option<&str>) -> PathBuf {
    arg.map(PathBuf::from)
        .or_else(|| env::var_os("LIFETXT_FILE").map(PathBuf::from))
        .unwrap_or_else(|| PathBuf::from("life.txt"))
}
fn print_record(r: &Record) {
    let f = r
        .fields
        .iter()
        .map(|(k, v)| format!("{k}:{v}"))
        .collect::<Vec<_>>()
        .join(" ");
    println!("[{}] {} {} {}", r.status, r.kind, r.title, f);
}
fn escaped(value: &str) -> String {
    value.replace('\\', "\\\\").replace('"', "\\\"")
}
fn atomic_mutate(path: &Path, original: &[u8], replacement: &[u8]) -> Result<(), String> {
    let meta = fs::symlink_metadata(path).map_err(|e| format!("{}: {e}", path.display()))?;
    if meta.file_type().is_symlink() {
        return Err("refusing to mutate a symbolic link".into());
    }
    if fs::read(path).map_err(|e| e.to_string())? != original {
        return Err("source changed since it was read".into());
    }
    let parent = path.parent().unwrap_or_else(|| Path::new("."));
    let stamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    let temp = parent.join(format!(
        ".{}.lifetxt-mini-{stamp}.tmp",
        path.file_name()
            .and_then(|v| v.to_str())
            .unwrap_or("life.txt")
    ));
    let result = (|| {
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&temp)
            .map_err(|e| e.to_string())?;
        file.write_all(replacement).map_err(|e| e.to_string())?;
        file.sync_all().map_err(|e| e.to_string())?;
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            fs::set_permissions(&temp, fs::Permissions::from_mode(meta.permissions().mode()))
                .map_err(|e| e.to_string())?;
        }
        fs::rename(&temp, path).map_err(|e| e.to_string())?;
        #[cfg(unix)]
        {
            let dir = std::fs::File::open(parent).map_err(|e| e.to_string())?;
            dir.sync_all().map_err(|e| e.to_string())?;
        }
        Ok::<(), String>(())
    })();
    if result.is_err() {
        let _ = fs::remove_file(&temp);
    }
    result
}
fn done_source(source: &str, wanted: &str) -> Result<String, String> {
    let document = parse(source)?;
    let rs = records(&document);
    let matches: Vec<_> = rs.into_iter().filter(|r| id(r) == Some(wanted)).collect();
    if matches.len() > 1 {
        return Err(format!("duplicate id: {wanted}"));
    }
    let Some(target) = matches.first() else {
        return Err(format!("record not found: {wanted}"));
    };
    if target.kind != 'T' || target.status != ' ' {
        return Err("done requires an open Mini Task".into());
    }
    let line = source
        .split_inclusive('\n')
        .nth(target.line - 1)
        .ok_or("target line missing")?;
    let offset = source
        .split_inclusive('\n')
        .take(target.line - 1)
        .map(str::len)
        .sum::<usize>();
    let marker = line.find("[ ]").ok_or("target status marker missing")?;
    let mut out = source.to_string();
    out.replace_range(offset + marker..offset + marker + 3, "[x]");
    Ok(out)
}
fn add_source(
    source: &str,
    title: &str,
    kind: char,
    fields: &[(String, String)],
) -> Result<String, String> {
    if title.is_empty() {
        return Err("title must not be empty".into());
    }
    let doc = parse(source)?;
    let existing: Vec<_> = records(&doc).iter().filter_map(|r| id(r)).collect();
    if fields
        .iter()
        .any(|(k, v)| k == "id" && existing.contains(&v.as_str()))
    {
        return Err("duplicate id".into());
    }
    if fields.iter().any(|(k, _)| {
        !matches!(
            k.as_str(),
            "id" | "due" | "on" | "from" | "to" | "project" | "tag"
        )
    }) {
        return Err("unsupported detail".into());
    }
    let mut record = format!("[ ] {kind} \"{}\"", escaped(title));
    for (k, v) in fields {
        record.push_str(&format!(
            " {k}:{}",
            if v.contains(char::is_whitespace) {
                format!("\"{}\"", escaped(v))
            } else {
                v.clone()
            }
        ));
    }
    let separator = if source.is_empty() || source.ends_with('\n') || source.ends_with('\r') {
        ""
    } else {
        "\n"
    };
    let newline = if source.contains("\r\n") {
        "\r\n"
    } else {
        "\n"
    };
    let mut out = source.to_string();
    out.push_str(separator);
    out.push_str(&record);
    out.push_str(newline);
    Ok(out)
}
fn main() -> io::Result<()> {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.is_empty() {
        eprintln!("usage: lifetxt-mini <list|show|check> [--id=<id>] [path]");
        std::process::exit(2);
    }
    let command = args[0].as_str();
    if command == "add" {
        let mut title = None;
        let mut kind = 'T';
        let mut fields = Vec::new();
        let mut path_arg = None;
        let mut i = 1;
        while i < args.len() {
            match args[i].as_str() {
                "--type" => {
                    i += 1;
                    kind = match args.get(i).map(String::as_str) {
                        Some("task") => 'T',
                        Some("event") => 'E',
                        Some("note") => 'N',
                        _ => {
                            eprintln!("--type must be task, event, or note");
                            std::process::exit(2)
                        }
                    };
                }
                "--id" | "--due" | "--on" | "--from" | "--to" | "--project" | "--tag" => {
                    let key = args[i].trim_start_matches("--").to_string();
                    i += 1;
                    let value = args.get(i).cloned().unwrap_or_else(|| {
                        eprintln!("missing value for --{key}");
                        std::process::exit(2)
                    });
                    fields.push((key, value));
                }
                value if value.starts_with("--") => {
                    eprintln!("unsupported add argument");
                    std::process::exit(2)
                }
                value if title.is_none() => title = Some(value.to_string()),
                value => path_arg = Some(value),
            }
            i += 1;
        }
        let path = resolve(path_arg);
        let original = fs::read(&path)?;
        let source = String::from_utf8(original.clone())
            .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "invalid UTF-8"))?;
        let replacement = add_source(&source, title.as_deref().unwrap_or(""), kind, &fields)
            .map_err(|e| io::Error::new(io::ErrorKind::InvalidInput, e))?;
        atomic_mutate(&path, &original, replacement.as_bytes())
            .map_err(|e| io::Error::new(io::ErrorKind::Other, e))?;
        return Ok(());
    }
    let mut path_arg = None;
    let mut selector = None;
    for a in &args[1..] {
        if let Some(v) = a.strip_prefix("--id=") {
            selector = Some(v)
        } else if a.starts_with('-') {
            eprintln!("Mini Runtime Profile: unsupported argument `{a}`");
            std::process::exit(2)
        } else {
            path_arg = Some(a.as_str())
        }
    }
    let path = resolve(path_arg);
    let original = fs::read(&path)?;
    let source = String::from_utf8(original.clone())
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "invalid UTF-8"))?;
    let doc = parse(&source).map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;
    let rs = records(&doc);
    let mut ids = HashMap::new();
    for r in &rs {
        if let Some(v) = id(r) {
            if ids.insert(v, r.line).is_some() && (command == "show" || selector.is_some()) {
                eprintln!("duplicate id: {v}");
                std::process::exit(1)
            }
        }
    }
    match command {
        "list" => {
            for r in rs {
                print_record(r)
            }
        }
        "show" => {
            let wanted = selector
                .or_else(|| args.get(1).map(String::as_str))
                .unwrap_or_else(|| {
                    eprintln!("show requires --id=<id>");
                    std::process::exit(2)
                });
            match rs.into_iter().find(|r| id(r) == Some(wanted)) {
                Some(r) => print_record(r),
                None => {
                    eprintln!("record not found: {wanted}");
                    std::process::exit(1)
                }
            }
        }
        "check" => println!("Mini Runtime Profile: OK (unsupported records skipped)"),
        "done" => {
            let wanted = selector
                .or_else(|| args.get(1).map(String::as_str))
                .unwrap_or_else(|| {
                    eprintln!("done requires an exact id");
                    std::process::exit(2)
                });
            let replacement = done_source(&source, wanted).unwrap_or_else(|e| {
                eprintln!("{e}");
                std::process::exit(1)
            });
            atomic_mutate(&path, &original, replacement.as_bytes()).unwrap_or_else(|e| {
                eprintln!("{e}");
                std::process::exit(1)
            });
        }
        _ => {
            eprintln!("unknown command: {command}");
            std::process::exit(2)
        }
    }
    Ok(())
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn unicode_and_repeated() {
        let d = parse("[ ] T \"東京\" id:a tag:x tag:y\n").unwrap();
        let r = records(&d)[0];
        assert_eq!(r.title, "東京");
        assert_eq!(r.fields.len(), 3)
    }
    #[test]
    fn opaque() {
        let d = parse("[/] H \"habit\" repeat:daily\n").unwrap();
        assert!(matches!(d.spans[0], Span::Opaque(_)))
    }
    #[test]
    fn malformed() {
        assert!(parse("[ ] T title bad\n").is_err())
    }

    #[test]
    fn mixed_fixture_keeps_opaque_and_body_spans() {
        let source = include_str!("../fixtures/mixed-life.txt");
        let document = parse(source).unwrap();
        assert!(document
            .spans
            .iter()
            .any(|span| matches!(span, Span::Opaque(_))));
        assert!(document
            .spans
            .iter()
            .any(|span| matches!(span, Span::Body(_))));
        assert!(document
            .spans
            .iter()
            .any(|span| matches!(span, Span::Comment(_))));
    }

    #[test]
    fn done_changes_only_the_status_marker() {
        let source = "# c\r\n[ ] T \"東京\" id:t1 tag:a tag:b\r\n| body\r\n";
        let actual = done_source(source, "t1").unwrap();
        assert_eq!(
            actual,
            "# c\r\n[x] T \"東京\" id:t1 tag:a tag:b\r\n| body\r\n"
        );
    }

    #[test]
    fn add_preserves_missing_final_newline_and_uses_existing_line_ending() {
        let actual = add_source("[ ] T \"A\" id:a\r\n", "B", 'N', &[]).unwrap();
        assert_eq!(actual, "[ ] T \"A\" id:a\r\n[ ] N \"B\"\r\n");
        let actual = add_source("[ ] T \"A\" id:a", "B", 'T', &[]).unwrap();
        assert_eq!(actual, "[ ] T \"A\" id:a\n[ ] T \"B\"\n");
    }

    #[test]
    fn duplicate_and_unsupported_done_targets_fail() {
        assert!(done_source("[ ] T A id:x\n[ ] T B id:x\n", "x").is_err());
        assert!(done_source("[x] T A id:x\n", "x").is_err());
        assert!(done_source("[/] H A id:x\n", "x").is_err());
    }
}
