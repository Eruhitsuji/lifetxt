use std::{collections::HashMap, env, fs, io, path::PathBuf};

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
fn main() -> io::Result<()> {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.is_empty() {
        eprintln!("usage: lifetxt-mini <list|show|check> [--id=<id>] [path]");
        std::process::exit(2);
    }
    let command = args[0].as_str();
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
    let source = String::from_utf8(fs::read(&path)?)
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
}
