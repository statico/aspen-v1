#!/usr/bin/env perl
use strict;
use warnings;
use utf8;

setpriority 0, 0, 40;

use CGI::Carp qw(fatalsToBrowser);
use CGI::Fast;
use Data::Pageset;
use HTML::HTML5::Entities qw(encode_entities);

use KinoSearch::Highlight::Highlighter;
use KinoSearch::Search::ANDQuery;
use KinoSearch::Search::SortRule;
use KinoSearch::Search::SortSpec;
use KinoSearch::Search::TermQuery;
use KinoSearch::Searcher;

my $path_to_index = '/var/data/aspen/db';
my $base_url      = '/content';

my $searcher = KinoSearch::Searcher->new( index => $path_to_index, );
my $sort_spec = KinoSearch::Search::SortSpec->new(
    rules => [
        KinoSearch::Search::SortRule->new( field => 'filename' ),
        KinoSearch::Search::SortRule->new( type  => 'doc_id' ),
    ]
);

my $qparser = KinoSearch::QueryParser->new(
    schema         => $searcher->get_schema,
    default_boolop => 'AND'
);
$qparser->set_heed_colons(1);

while ( my $cgi = new CGI::Fast ) {
    my $q      = $cgi->param('q')      || '';
    my $offset = $cgi->param('offset') || 0;
    my $path   = $cgi->param('path');
    my $sort_by_filename = $cgi->param('alpha') ? '1' : '';
    my $hits_per_page = 10;

    my $query_obj = $qparser->parse($q);
    if ($path) {
        my $filename_query = KinoSearch::Search::TermQuery->new(
            field => 'filename',
            term  => $path,
        );
        $query_obj = KinoSearch::Search::ANDQuery->new(
            children => [ $query_obj, $filename_query ] );
    }

    my $hits = $searcher->hits(
        query      => $query_obj,
        offset     => $offset,
        num_wanted => $hits_per_page,
        $sort_by_filename ? ( sort_spec => $sort_spec ) : (),
    );
    my $total_hits = $hits->total_hits;

    my $highlighter = KinoSearch::Highlight::Highlighter->new(
        searcher       => $searcher,
        query          => $q,
        field          => 'content',
        excerpt_length => 1000,
    );

    my $report = '';
    while ( my $hit = $hits->next ) {
        my $score    = sprintf( "%0.3f", $hit->get_score );
        my $url      = encode_entities( $hit->{url} );
        my $filename = encode_entities( $hit->{filename} );
        my $excerpt  = $highlighter->create_excerpt($hit);
        $report .= qq|
        <dt>
            <a href="$url"><strong>$filename</strong></a>
            <em>(Score: $score)</em>
        </dt>
        <dd>$excerpt</dd>
        |;
    }
    $report = "<dl>$report</dl>";

    my $query_string = encode_entities($q);
    my $paging_info;
    my $inpath_message = $path ? "in <strong>$path</strong>" : '';
    if ( !length $query_string ) {
        $paging_info = '';
    }
    elsif ( $total_hits == 0 ) {
        $paging_info
            = qq|<p class="nav">No matches for <strong>$query_string</strong> $inpath_message</p>|;
    }
    else {
        my $current_page = ( $offset / $hits_per_page ) + 1;
        my $pager        = Data::Pageset->new(
            {   total_entries    => $total_hits,
                entries_per_page => $hits_per_page,
                current_page     => $current_page,
                pages_per_set    => 10,
                mode             => 'slide',
            }
        );
        my $last_result  = $pager->last;
        my $first_result = $pager->first;

        # Display the result nums, start paging info.
        $paging_info = qq|
        <p class="nav">
            Results <strong>$first_result-$last_result</strong>
            of <strong>$total_hits</strong> for <strong>$query_string $inpath_message</strong>
            &nbsp; &mdash; &nbsp;
            Page:
        |;

        # Create a url for use in paging links.
        my $params = $cgi->query_string;
        $params =~ s/;/&amp;/g;
        my $href = $cgi->url( -relative => 1 ) . "?$params";
        $href .= "&amp;offset=0" unless $href =~ /offset=/;

        # Generate the "Prev" link.
        if ( $current_page > 1 ) {
            my $new_offset = ( $current_page - 2 ) * $hits_per_page;
            $href =~ s/(?<=offset=)\d+/$new_offset/;
            $paging_info .= qq|<a href="$href">&laquo; Prev</a>\n|;
        }

        # Generate paging links.
        for my $page_num ( @{ $pager->pages_in_set } ) {
            if ( $page_num == $current_page ) {
                $paging_info .= qq|$page_num \n|;
            }
            else {
                my $new_offset = ( $page_num - 1 ) * $hits_per_page;
                $href =~ s/(?<=offset=)\d+/$new_offset/;
                $paging_info .= qq|<a href="$href">$page_num</a>\n|;
            }
        }

        # Generate the "Next" link.
        if ( $current_page != $pager->last_page ) {
            my $new_offset = $current_page * $hits_per_page;
            $href =~ s/(?<=offset=)\d+/$new_offset/;
            $paging_info .= qq|<a href="$href">Next &raquo;</a>\n|;
        }

        # Close tag.
        $paging_info .= "</p>\n";
    }

    my $sort_by_filename_checked = $sort_by_filename ? 'checked="yes"' : '';
    my $remote_user = $cgi->remote_user || 'UNKNOWN';
    my $title = ( $q ? "$query_string - " : '' ) . 'Aspen Search';

    print $cgi->header( -charset => 'ISO-8859-1' );
    print <<END_HTML;
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
    "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
    <title>$title</title>
    <link rel="stylesheet"  href="/style.css" type="text/css"/>
</head>

<body>
    <h1>
        Aspen Search
    </h1>

    <div>
        <form id="form" action="">
            <strong>Search:</strong>
            <input type="text" name="q" id="q" value="$query_string"/>
            <input type="submit" value="Search"/>
            <input type="hidden" name="offset" value="0"/>
            <input type="checkbox" name="alpha" id="alpha"
                value="1" $sort_by_filename_checked
                onchange="this.form.submit(); return true;"
                />
            <label for="alpha">Sort by filename?</label>
            &nbsp;
            <a href="/ebooks">Browse ebooks</a>
        </form>
    </div>

    <div id="content">

    $paging_info
    $report
    $paging_info

    </div><!--content-->

    <script type="text/javascript">
    window.onload = function() {
        document.getElementById('q').focus();
    };
    </script>

</body>

</html>
END_HTML
}
