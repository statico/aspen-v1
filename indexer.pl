#!/usr/bin/env perl
use strict;
use warnings;

use File::Find::Rule;
use File::Spec;

use KinoSearch::Analysis::PolyAnalyzer;
use KinoSearch::FieldType::FullTextType;
use KinoSearch::FieldType::StringType;
use KinoSearch::Indexer;
use KinoSearch::Schema;

my $path_to_index = '/var/data/aspen/db';
my $base_url      = '/content';

my $source_dir    = '/var/data/aspen/www';
my $path_to_index = '/var/data/aspen/db';
my $base_url      = '/content';

my $schema = KinoSearch::Schema->new;
my $polyanalyzer
    = KinoSearch::Analysis::PolyAnalyzer->new( language => 'en', );

my $content_type = KinoSearch::FieldType::FullTextType->new(
    analyzer      => $polyanalyzer,
    highlightable => 1,
);
my $metadata_type
    = KinoSearch::FieldType::StringType->new( sortable => 1, indexed => 0 );
my $filename_type
    = KinoSearch::FieldType::StringType->new( sortable => 1, indexed => 1 );
$schema->spec_field( name => 'content',  type => $content_type );
$schema->spec_field( name => 'url',      type => $metadata_type );
$schema->spec_field( name => 'filename', type => $filename_type );

my $indexer = KinoSearch::Indexer->new(
    index    => $path_to_index,
    schema   => $schema,
    create   => 1,
    truncate => 1,
);

$SIG{INT} = sub {
    warn "\n\nInterrupted... finishing indexer.\n";
    $indexer->commit;
    exit;
};

sub parse_file {
    my $filename = shift;
    my $filepath = File::Spec->catfile( $source_dir, $filename );
    open( my $fh, '<', $filepath )
        or die "couldn't open file '$filepath': $!";
    my $content = do { local $/; <$fh> };
    return {
        content  => $content,
        url      => "$base_url/$filename",
        filename => $filename,
    };
}

my @filenames
    = File::Find::Rule->file()->name('*.txt')->relative()->in($source_dir);
die "No files found to index" unless @filenames;
print "About to index " . @filenames . " files...\n" if -t STDOUT;

foreach my $filename (@filenames) {
    $indexer->add_doc( parse_file($filename) );
    print "Indexed $filename\n" if -t STDOUT;
}

$indexer->commit;
print "Done.\n" if -t STDOUT;
